#!/bin/bash
# Add or remove piroTalk from Ubuntu autostart (login startup)
# Usage:
#   ./autostart.sh           — enable autostart (iGPU, default)
#   ./autostart.sh --npu     — enable autostart (NPU)
#   ./autostart.sh --remove  — disable autostart

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUTOSTART_FILE="$HOME/.config/autostart/pirotalk.desktop"

if [ "$1" = "--remove" ]; then
    if [ -f "$AUTOSTART_FILE" ]; then
        rm "$AUTOSTART_FILE"
        echo "piroTalk removed from autostart."
    else
        echo "piroTalk was not in autostart."
    fi
    exit 0
fi

if [ "$1" = "--npu" ]; then
    EXEC="/usr/bin/python3 ${SCRIPT_DIR}/pirotalk_npu.py"
else
    EXEC="${SCRIPT_DIR}/.venv/bin/python3 ${SCRIPT_DIR}/pirotalk_igpu.py"
fi

mkdir -p "$HOME/.config/autostart"

cat > "$AUTOSTART_FILE" << EOF
[Desktop Entry]
Type=Application
Name=piroTalk Voice-to-Type
Comment=Hold Pause to dictate, speech typed into focused app
Exec=${EXEC}
Icon=${SCRIPT_DIR}/icons/ready.png
Terminal=false
Categories=Utility;Accessibility;
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
EOF

echo "piroTalk will start automatically on next login."
echo "Entry: $AUTOSTART_FILE"
