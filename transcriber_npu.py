"""Whisper NPU transcriber - encoder on Intel NPU via OpenVINO, decoder on CPU."""

import os
import numpy as np
import torch
import whisper
import openvino as ov

WHISPER_MODEL = "base"
LANGUAGE = "en"
CACHE_DIR = os.path.expanduser("~/.cache/whisper")
OV_DIR = os.path.join(CACHE_DIR, "openvino")


class NpuTranscriber:
    """Whisper encoder on Intel NPU (OpenVINO), decoder on CPU."""

    def __init__(self):
        self.model = None
        self.compiled_encoder = None
        self._original_encoder_forward = None

    def _onnx_path(self):
        return os.path.join(OV_DIR, f"encoder_{WHISPER_MODEL}_static.onnx")

    def load(self):
        print(f"Loading Whisper {WHISPER_MODEL} model...")
        self.model = whisper.load_model(WHISPER_MODEL, device="cpu",
                                        download_root=CACHE_DIR)
        self._original_encoder_forward = self.model.encoder.forward

        onnx_path = self._onnx_path()
        if not os.path.exists(onnx_path):
            print("Exporting Whisper encoder to ONNX (one-time)...")
            os.makedirs(OV_DIR, exist_ok=True)
            mel_input = torch.randn(1, self.model.dims.n_mels, 3000)
            with torch.no_grad():
                torch.onnx.export(self.model.encoder, mel_input, onnx_path,
                                  input_names=["mel"], output_names=["output"],
                                  opset_version=18)

        print("Compiling encoder for NPU...")
        core = ov.Core()
        ov_model = core.read_model(onnx_path)
        self.compiled_encoder = core.compile_model(ov_model, "NPU")
        print("Ready.")

    def encode(self, audio_np):
        """Process audio and run Whisper encoder on NPU. Returns (mel, audio_features)."""
        audio_np = audio_np.flatten().astype(np.float32)
        audio_tensor = whisper.pad_or_trim(torch.from_numpy(audio_np))
        mel = whisper.log_mel_spectrogram(audio_tensor,
                                           self.model.dims.n_mels).unsqueeze(0)
        npu_out = self.compiled_encoder(mel.numpy().astype(np.float32))[0]
        audio_features = torch.from_numpy(np.array(npu_out))
        return mel, audio_features

    def decode(self, encode_result):
        """Run Whisper decoder on CPU. Returns transcribed text."""
        mel, audio_features = encode_result
        captured = audio_features  # capture for closure
        self.model.encoder.forward = lambda _mel: captured
        options = whisper.DecodingOptions(language=LANGUAGE, fp16=False)
        result = whisper.decode(self.model, mel, options)
        self.model.encoder.forward = self._original_encoder_forward
        text = result[0].text if isinstance(result, list) else result.text
        return text.strip()
