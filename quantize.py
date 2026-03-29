#!/home/lucas/ai/mic/.venv/bin/python3
"""
Export and INT4-quantize the CohereASR model for Intel iGPU.

Downloads the model from Hugging Face on first run (~8 GB), then exports
the encoder and decoder to OpenVINO with INT4 weight quantization via NNCF.
Output is saved to ~/.cache/cohere-asr/openvino/ (~1.2 GB total).

Run this once before using mic_igpu.py for the first time.
Re-running is safe — it skips files that already exist.

Usage:
    ./quantize.py                                    # use MODEL_ID from transcriber_igpu.py
    ./quantize.py /path/to/local/model               # custom local path
    ./quantize.py CohereLabs/cohere-transcribe-03-2026  # Hugging Face repo ID
    ./quantize.py --force                            # re-export even if cache exists
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
import transcriber_igpu as ti
from transcriber_igpu import CohereTranscriber
from transformers import AutoProcessor, CohereAsrForConditionalGeneration

force = "--force" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
model_id = args[0] if args else ti.MODEL_ID

# Remove cached files if forcing re-export
if force:
    for f in [
        ti.OV_ENCODER_PATH, ti.OV_ENCODER_PATH.replace(".xml", ".bin"),
        ti.OV_DECODER_PATH, ti.OV_DECODER_PATH.replace(".xml", ".bin"),
    ]:
        if os.path.exists(f):
            os.remove(f)
            print(f"Removed {f}")

if all(os.path.exists(p) for p in [ti.OV_ENCODER_PATH, ti.OV_DECODER_PATH]):
    print("INT4 models already exist. Use --force to re-export.")
    sys.exit(0)

print(f"Loading model: {model_id}")
print("(First run downloads ~8 GB from Hugging Face — this may take a while)")
print()

t = CohereTranscriber()
t.processor = AutoProcessor.from_pretrained(model_id)
t.model = CohereAsrForConditionalGeneration.from_pretrained(
    model_id, torch_dtype=torch.float32
)

if not os.path.exists(ti.OV_ENCODER_PATH):
    print("Exporting Parakeet encoder to OpenVINO INT4...")
    print("(This takes 10-20 minutes — the model is 2B parameters)")
    t._export_encoder()
    size = os.path.getsize(ti.OV_ENCODER_PATH.replace(".xml", ".bin")) / 1e9
    print(f"Encoder saved: {ti.OV_ENCODER_PATH} ({size:.1f} GB)")
    print()

if not os.path.exists(ti.OV_DECODER_PATH):
    print("Exporting Cohere decoder to OpenVINO INT4...")
    t._export_decoder()
    size = os.path.getsize(ti.OV_DECODER_PATH.replace(".xml", ".bin")) / 1e6
    print(f"Decoder saved: {ti.OV_DECODER_PATH} ({size:.0f} MB)")
    print()

print(f"Done. Models saved to: {ti.OV_CACHE_DIR}")
print("You can now run mic_igpu.py")
