"""NPU Whisper transcriber -- encoder on Intel NPU, decoder on CPU."""

import os
import numpy as np
import torch
import whisper
import openvino as ov

WHISPER_MODEL = "base"
CACHE_DIR = os.path.expanduser("~/.cache/whisper")
OV_DIR = os.path.join(CACHE_DIR, "openvino")


class NpuTranscriber:
    """Loads whisper model once, keeps NPU encoder compiled and warm."""

    def __init__(self):
        self.model = None
        self.compiled_encoder = None
        self._original_forward = None

    def _onnx_path(self):
        return os.path.join(OV_DIR, f"encoder_{WHISPER_MODEL}_static.onnx")

    def load(self):
        """Load whisper model on CPU, export encoder to ONNX, compile for NPU."""
        self.model = whisper.load_model(WHISPER_MODEL, device="cpu",
                                        download_root=CACHE_DIR)
        self.model.eval()
        self._original_forward = self.model.encoder.forward

        onnx_path = self._onnx_path()
        if not os.path.exists(onnx_path):
            os.makedirs(OV_DIR, exist_ok=True)
            mel_input = torch.randn(1, self.model.dims.n_mels, 3000)
            with torch.no_grad():
                torch.onnx.export(self.model.encoder, mel_input, onnx_path,
                                  input_names=["mel"], output_names=["output"],
                                  opset_version=18)

        core = ov.Core()
        ov_model = core.read_model(onnx_path)
        self.compiled_encoder = core.compile_model(ov_model, "NPU")

    def transcribe(self, audio_np):
        """Transcribe a numpy float32 array (16kHz mono) to text."""
        audio_np = audio_np.flatten().astype(np.float32)
        audio_tensor = torch.from_numpy(audio_np)
        audio_tensor = whisper.pad_or_trim(audio_tensor)
        mel = whisper.log_mel_spectrogram(audio_tensor,
                                          self.model.dims.n_mels).unsqueeze(0)

        # Encoder on NPU
        npu_output = self.compiled_encoder(mel.numpy().astype(np.float32))[0]
        audio_features = torch.from_numpy(np.array(npu_output))

        # Patch encoder to return NPU result
        self.model.encoder.forward = lambda _mel: audio_features

        # Decoder on CPU
        options = whisper.DecodingOptions(language="en", fp16=False)
        result = whisper.decode(self.model, mel, options)

        # Restore
        self.model.encoder.forward = self._original_forward

        text = result[0].text if isinstance(result, list) else result.text
        return text.strip()
