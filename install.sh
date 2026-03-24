#!/bin/bash
# Install mic voice-to-type daemon for autostart on login
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== mic voice-to-type installer ==="
echo ""

# System packages
echo "Installing system packages..."
sudo apt-get install -y ffmpeg libportaudio2 gir1.2-ayatanaappindicator3-0.1

# Python packages
echo "Installing Python packages..."
pip install --break-system-packages sounddevice evdev openai-whisper openvino torch numpy PyGObject

# Input group
if ! groups "$USER" | grep -q '\binput\b'; then
    echo "Adding $USER to input group..."
    sudo usermod -aG input "$USER"
    echo "NOTE: Log out and back in for group change to take effect."
fi

# uinput permission (persistent across reboots)
if [ ! -f /etc/udev/rules.d/99-uinput.rules ]; then
    echo "Setting up /dev/uinput permissions..."
    echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger
fi
sudo chmod 0666 /dev/uinput

# Autostart desktop entry
echo "Installing autostart entry..."
mkdir -p ~/.config/autostart
sed "s|Exec=.*|Exec=/usr/bin/python3 ${SCRIPT_DIR}/mic.py|" \
    "${SCRIPT_DIR}/mic.desktop" > ~/.config/autostart/mic.desktop

# Log directory
mkdir -p ~/.local/share/mic

echo ""
echo "=== Installation complete ==="
echo ""
echo "Logs:      ~/.local/share/mic/mic.log"
echo "Autostart: ~/.config/autostart/mic.desktop"
echo ""
echo "To start now:  python3 ${SCRIPT_DIR}/mic.py &"
echo "It will auto-start on next login."
