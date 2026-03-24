# mic - NPU Voice-to-Type for Linux

Hold a key, speak, release — your words appear wherever your cursor is. Speech recognition runs on the Intel NPU via OpenVINO, keeping your CPU and GPU free.

## How it works

```
Hold Pause key → record from microphone
                      ↓
Release Pause  → whisper encoder runs on Intel NPU (~0.12s)
                      ↓
                 whisper decoder runs on CPU (~0.16s)
                      ↓
                 text typed into focused app via virtual keyboard
```

A system tray icon shows the current state:
- **Grey** — loading model
- **Green** — ready
- **Red** — recording
- **Yellow** — transcribing

## Requirements

- Ubuntu 24.04 (Wayland/GNOME)
- Intel CPU with NPU (Arrow Lake / Lunar Lake / Meteor Lake)
- NPU driver installed (`intel_vpu` kernel module, `/dev/accel/accel0` present)
- Python 3.12+

## Installation

```bash
# System packages
sudo apt-get install -y ffmpeg libportaudio2 gir1.2-ayatanaappindicator3-0.1

# Python packages
pip install --break-system-packages sounddevice evdev openai-whisper openvino torch numpy PyGObject

# Add your user to the input group (required for hotkey detection and virtual keyboard)
sudo usermod -aG input $USER
# Make uinput accessible (required for virtual keyboard output)
sudo chmod 0666 /dev/uinput
```

**Log out and back in** after the group change.

To make the `/dev/uinput` permission persistent across reboots:

```bash
echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules
```

## Usage

```bash
python3 mic.py
```

1. Wait for the tray icon to turn **green**
2. Hold **Pause** key and speak
3. Release — transcribed text appears at your cursor

## Configuration

Edit the constants at the top of each file:

| File | Constant | Default | Description |
|---|---|---|---|
| `mic.py` | `HOTKEY_CODE` | `119` (Pause) | evdev keycode for the hold-to-talk key |
| `mic.py` | `MIC_DEVICE` | `FHD Camera Microphone` | Microphone name substring |
| `transcriber.py` | `WHISPER_MODEL` | `base` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large`) |
| `typer.py` | `DVORAK_MAP` | Dvorak-intl | Keyboard layout character-to-keycode map |

## Architecture

```
mic.py           — main daemon: state machine, GTK tray icon, evdev hotkey listener,
                   audio capture via sounddevice, orchestrates everything
transcriber.py   — NPU whisper engine: loads model, exports encoder to ONNX,
                   compiles for NPU, runs encoder on NPU + decoder on CPU
typer.py         — virtual keyboard: types text into focused app via evdev UInput,
                   layout-aware (currently Dvorak-intl)
icons/           — tray icon PNGs for each state
```

## License

MIT
