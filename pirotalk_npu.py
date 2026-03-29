#!/usr/bin/env python3
"""NPU launcher: Whisper encoder on Intel NPU, decoder on CPU."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mic import VoiceTypeDaemon, setup_logging
from transcriber_npu import NpuTranscriber

if __name__ == "__main__":
    setup_logging("pirotalk_npu")
    VoiceTypeDaemon(NpuTranscriber).run()
