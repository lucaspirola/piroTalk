"""Cohere ASR transcriber - Parakeet encoder + decoder on Intel iGPU via OpenVINO."""

import os
import numpy as np
import torch
import nncf
import openvino as ov
from transformers import AutoProcessor, CohereAsrForConditionalGeneration
from transformers.models.parakeet.modeling_parakeet import ParakeetEncoderModelOutput
from transformers.modeling_outputs import BaseModelOutputWithPastAndCrossAttentions

MODEL_ID = "/home/lucas/ai/models/cohere-transcribe-03-2026"
OV_CACHE_DIR = os.path.expanduser("~/.cache/cohere-asr/openvino")
OV_ENCODER_PATH = os.path.join(OV_CACHE_DIR, "encoder.xml")
OV_DECODER_PATH = os.path.join(OV_CACHE_DIR, "decoder.xml")
LANGUAGE = "en"
OV_DEVICE = "GPU"


class _EncoderWrapper(torch.nn.Module):
    """Strips dataclass output so OV export sees plain tensors."""
    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder

    def forward(self, input_features, attention_mask):
        out = self.encoder(input_features, attention_mask=attention_mask,
                           output_attention_mask=True)
        return out.last_hidden_state, out.attention_mask


class _DecoderWrapper(torch.nn.Module):
    """Decoder body for OV/ONNX export.
    - Uses eager attention (SDPA+GQA not ONNX-exportable with torch 2.11)
    - Explicit causal mask (avoids create_causal_mask tracing crash)
    - lm_head (proj_out) stays on CPU
    """

    def __init__(self, decoder):
        super().__init__()
        self.proj = decoder.proj
        self.embed_tokens = decoder.embed_tokens
        self.pos_emb = decoder.pos_emb
        self.embedding_layernorm = decoder.embedding_layernorm
        self.layers = decoder.layers
        self.norm = decoder.norm

    def forward(self, input_ids, encoder_hidden_states):
        enc = self.proj(encoder_hidden_states)

        embeds = self.embed_tokens(input_ids)
        seq_len = embeds.shape[1]
        pos_ids = torch.arange(seq_len, device=embeds.device).unsqueeze(0)
        pos_emb = self.pos_emb(pos_ids.squeeze(0))
        hidden = self.embedding_layernorm(embeds + pos_emb)

        # Explicit causal mask: (1, 1, seq_len, seq_len), additive float bias
        idx = torch.arange(seq_len, device=hidden.device)
        causal_mask = (idx.unsqueeze(0) > idx.unsqueeze(1)).to(hidden.dtype) * -1e9
        causal_mask = causal_mask.unsqueeze(0).unsqueeze(0)

        for layer in self.layers:
            hidden = layer(
                hidden,
                causal_mask,
                encoder_hidden_states=enc,
                encoder_attention_mask=None,
                position_ids=pos_ids,
                past_key_values=None,
            )

        return self.norm(hidden)


class CohereTranscriber:
    """Parakeet encoder + Cohere decoder on Intel iGPU (OpenVINO)."""

    def __init__(self):
        self.processor = None
        self.model = None
        self.compiled_encoder = None
        self.compiled_decoder = None
        self._original_encoder_forward = None
        self._original_decoder_forward = None

    # --- Model loading ---

    def load(self):
        print("Loading Cohere ASR model...")
        self.processor = AutoProcessor.from_pretrained(MODEL_ID)
        self.model = CohereAsrForConditionalGeneration.from_pretrained(
            MODEL_ID, torch_dtype=torch.float32
        )

        # Encoder on iGPU
        if not os.path.exists(OV_ENCODER_PATH):
            print("Exporting Parakeet encoder to OpenVINO (one-time)...")
            self._export_encoder()

        print(f"Compiling encoder for {OV_DEVICE}...")
        core = ov.Core()
        ov_enc = core.read_model(OV_ENCODER_PATH)
        self.compiled_encoder = core.compile_model(ov_enc, OV_DEVICE)
        self._original_encoder_forward = self.model.model.encoder.forward
        self.model.model.encoder.forward = self._ov_encoder_forward

        # Decoder on iGPU
        if not os.path.exists(OV_DECODER_PATH):
            print("Exporting Cohere decoder to OpenVINO (one-time, ~2 min)...")
            self._export_decoder()

        print(f"Compiling decoder for {OV_DEVICE}...")
        ov_dec = core.read_model(OV_DECODER_PATH)
        self.compiled_decoder = core.compile_model(ov_dec, OV_DEVICE)
        self._original_decoder_forward = self.model.model.decoder.forward
        self.model.model.decoder.forward = self._ov_decoder_forward
        self.decoder_on_ov = True

        print("Ready.")

    # --- OV export ---

    def _export_encoder(self):
        os.makedirs(OV_CACHE_DIR, exist_ok=True)
        wrapper = _EncoderWrapper(self.model.model.encoder)
        dummy_raw = np.zeros(16000, dtype=np.float32)
        dummy_inputs = self.processor(dummy_raw, sampling_rate=16000, return_tensors="pt",
                                      language=LANGUAGE)
        dummy_audio = dummy_inputs["input_features"]
        dummy_mask = dummy_inputs.get("attention_mask",
                                      torch.ones(1, dummy_audio.shape[-1], dtype=torch.long))
        with torch.no_grad():
            ov_model = ov.convert_model(wrapper, example_input=(dummy_audio, dummy_mask))

        print("Quantizing encoder to INT4 (weight-only)...")
        ov_model = nncf.compress_weights(
            ov_model,
            mode=nncf.CompressWeightsMode.INT4_ASYM,
        )

        ov.save_model(ov_model, OV_ENCODER_PATH)

    def _export_decoder(self):
        os.makedirs(OV_CACHE_DIR, exist_ok=True)

        # Get actual encoder output shapes from a dummy encode
        dummy_raw = np.zeros(16000, dtype=np.float32)
        dummy_proc = self.processor(dummy_raw, sampling_rate=16000, return_tensors="pt",
                                    language=LANGUAGE)
        with torch.no_grad():
            enc_out = self.model.model.encoder(
                dummy_proc["input_features"],
                attention_mask=dummy_proc.get("attention_mask"),
            )
        enc_hidden = enc_out.last_hidden_state   # (1, enc_seq_len, enc_hidden_dim)

        bos_id = self.model.config.bos_token_id or self.processor.tokenizer.bos_token_id
        bos = torch.tensor([[bos_id]])
        decoder = self.model.model.decoder
        wrapper = _DecoderWrapper(decoder)

        # Temporarily use eager attention: SDPA+GQA is not exportable with torch 2.11
        orig_attn = decoder.config._attn_implementation
        decoder.config._attn_implementation = "eager"

        # Export via TorchScript tracing (dynamo=False avoids deadlocks on complex models)
        onnx_tmp = os.path.join(OV_CACHE_DIR, "_decoder_tmp.onnx")
        try:
          with torch.no_grad():
            torch.onnx.export(
                wrapper,
                (bos, enc_hidden),
                onnx_tmp,
                input_names=["input_ids", "encoder_hidden_states"],
                output_names=["last_hidden_state"],
                dynamic_axes={
                    "input_ids": {1: "seq_len"},
                    "encoder_hidden_states": {1: "enc_len"},
                },
                opset_version=14,
                dynamo=False,
            )

        finally:
            decoder.config._attn_implementation = orig_attn

        ov_model = ov.convert_model(onnx_tmp)

        # Clean up temp ONNX files (may have external .data sidecar for large models)
        for f in [onnx_tmp, onnx_tmp + ".data"]:
            if os.path.exists(f):
                os.remove(f)

        print("Quantizing decoder to INT4 (weight-only)...")
        ov_model = nncf.compress_weights(
            ov_model,
            mode=nncf.CompressWeightsMode.INT4_ASYM,
        )

        ov.save_model(ov_model, OV_DECODER_PATH)

    # --- OV forward replacements ---

    def _ov_encoder_forward(self, input_features, attention_mask=None, **kwargs):
        inputs = {"input_features": input_features.numpy()}
        if attention_mask is not None:
            inputs["attention_mask"] = attention_mask.numpy()
        result = self.compiled_encoder(inputs)
        last_hidden_state = torch.from_numpy(np.array(result[0]))
        out_mask = torch.from_numpy(np.array(result[1])) if len(result) > 1 else None
        return ParakeetEncoderModelOutput(
            last_hidden_state=last_hidden_state,
            attention_mask=out_mask,
        )

    def _ov_decoder_forward(self, input_ids=None, attention_mask=None, position_ids=None,
                             past_key_values=None, inputs_embeds=None, use_cache=None,
                             encoder_hidden_states=None, encoder_attention_mask=None, **kwargs):
        result = self.compiled_decoder({
            "input_ids": input_ids.numpy().astype(np.int64),
            "encoder_hidden_states": encoder_hidden_states.numpy().astype(np.float32),
        })
        last_hidden_state = torch.from_numpy(np.array(result[0]))
        return BaseModelOutputWithPastAndCrossAttentions(
            last_hidden_state=last_hidden_state,
        )

    # --- Transcription ---

    def encode(self, audio_np):
        """Process audio and run Parakeet encoder on iGPU. Returns (inputs, encoder_outputs)."""
        audio_np = audio_np.flatten().astype(np.float32)
        inputs = self.processor(
            audio_np, sampling_rate=16000, return_tensors="pt", language=LANGUAGE
        )
        with torch.no_grad():
            encoder_outputs = self.model.model.encoder(
                inputs["input_features"],
                attention_mask=inputs.get("attention_mask"),
            )
        return inputs, encoder_outputs

    def decode(self, encode_result):
        """Run Cohere decoder on iGPU (or CPU fallback). Returns transcribed text."""
        inputs, encoder_outputs = encode_result
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                encoder_outputs=encoder_outputs,
                max_new_tokens=448,
                use_cache=False,
            )
        result = self.processor.decode(outputs, skip_special_tokens=True)
        text = result[0] if isinstance(result, list) else result
        return text.strip()
