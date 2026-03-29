#!/bin/bash
# Install mic voice-to-type daemon
# Default: iGPU mode (CohereASR on Intel iGPU via OpenVINO)
# Optional: --npu for Whisper on Intel NPU
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODE="igpu"

for arg in "$@"; do
    case $arg in
        --npu) MODE="npu" ;;
        --igpu) MODE="igpu" ;;
    esac
done

echo "=== mic voice-to-type installer (mode: $MODE) ==="
echo ""

# System packages (common to both modes)
echo "Installing system packages..."
sudo apt-get install -y \
    ffmpeg \
    libportaudio2 \
    gir1.2-ayatanaappindicator3-0.1 \
    python3-pip \
    python3-venv \
    xdotool \
    wtype

if [ "$MODE" = "igpu" ]; then
    # iGPU mode: CohereASR in a dedicated virtualenv
    echo ""
    echo "Setting up Python virtualenv (.venv)..."
    python3 -m venv "${SCRIPT_DIR}/.venv"
    "${SCRIPT_DIR}/.venv/bin/pip" install --upgrade pip

    echo "Installing Python packages into .venv..."
    "${SCRIPT_DIR}/.venv/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt"

    LAUNCHER="${SCRIPT_DIR}/.venv/bin/python3 ${SCRIPT_DIR}/pirotalk_igpu.py"
    LOG_FILE="pirotalk_igpu.log"

else
    # NPU mode: Whisper with system Python
    echo ""
    echo "Installing Python packages (system-wide)..."
    pip3 install --break-system-packages -r "${SCRIPT_DIR}/requirements_npu.txt"

    LAUNCHER="/usr/bin/python3 ${SCRIPT_DIR}/pirotalk_npu.py"
    LOG_FILE="pirotalk_npu.log"
fi

# Input group (needed by both modes for the Pause key listener)
if ! groups "$USER" | grep -q '\binput\b'; then
    echo ""
    echo "Adding $USER to input group..."
    sudo usermod -aG input "$USER"
    echo "NOTE: Log out and back in for group change to take effect."
fi

# Autostart desktop entry
echo ""
echo "Installing autostart entry..."
mkdir -p ~/.config/autostart
sed "s|Exec=.*|Exec=${LAUNCHER}|" \
    "${SCRIPT_DIR}/mic.desktop" > ~/.config/autostart/mic.desktop

# Log directory
mkdir -p ~/.local/share/mic

echo ""
echo "=== Installation complete (mode: $MODE) ==="
echo ""
echo "Log:       ~/.local/share/mic/${LOG_FILE}"
echo "Autostart: ~/.config/autostart/mic.desktop"
echo ""

if [ "$MODE" = "igpu" ]; then
    echo "Next steps:"
    echo "  1. Download the model from Hugging Face (if not already done):"
    echo "       huggingface-cli download CohereLabs/cohere-transcribe-03-2026 \\"
    echo "           --local-dir ~/models/cohere-transcribe-03-2026"
    echo "  2. Update MODEL_ID in transcriber_igpu.py to point to your model path"
    echo "  3. Run the quantizer (one-time, takes 10-20 min):"
    echo "       ./quantize.py"
    echo "  4. Start the daemon:"
    echo "       ./pirotalk_igpu.py &"
    echo ""
    echo "The daemon will auto-start on next login."
else
    echo "To start now:"
    echo "  python3 ${SCRIPT_DIR}/pirotalk_npu.py &"
    echo ""
    echo "The daemon will auto-start on next login."
fi
