#!/home/lucas/ai/mic/.venv/bin/python3
"""iGPU launcher: Parakeet encoder + Cohere decoder on Intel iGPU via OpenVINO."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mic import VoiceTypeDaemon, setup_logging
from transcriber_igpu import CohereTranscriber

if __name__ == "__main__":
    setup_logging("mic_igpu")
    VoiceTypeDaemon(CohereTranscriber).run()
