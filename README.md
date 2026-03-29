# piroTalk - Voice-to-Type for Linux

Hold **Pause**, speak, release — transcribed text appears wherever your cursor is.
The hold-to-talk key is configurable (see [Changing the hotkey](#changing-the-hotkey)).

Runs entirely on local hardware. Two backends available:

| Mode | Model | Hardware | Quality |
|---|---|---|---|
| **iGPU** (default) | CohereASR 2B (Parakeet + Cohere decoder) | Intel integrated GPU | High accuracy, 14 languages |
| **NPU** | Whisper | Intel NPU (Arrow Lake / Meteor Lake) | Fast, 100 languages |

---

## Requirements

- **OS**: Ubuntu 24.04 (Wayland or X11)
- **Common**: `xdotool`, `wtype`, `libportaudio2`, `gir1.2-ayatanaappindicator3-0.1`

**iGPU mode** additionally requires:
- Intel integrated GPU supported by OpenVINO
- OpenVINO GPU driver (`intel_gpu` via Mesa or oneAPI)
- ~1.4 GB iGPU VRAM for the INT4 quantized models
- ~8 GB free disk space to download the model from Hugging Face

**NPU mode** additionally requires:
- Intel NPU (Arrow Lake / Lunar Lake / Meteor Lake)
- NPU driver installed (`intel_vpu` kernel module, `/dev/accel/accel0` present)

---

## Quick Start — iGPU (default)

### 1. Clone and install dependencies

```bash
git clone https://github.com/lucaspirola/piroTalk.git
cd mic
./install.sh
```

This creates a `.venv` and installs all Python dependencies into it.

### 2. Download the model

```bash
pip install huggingface-hub
huggingface-cli download CohereLabs/cohere-transcribe-03-2026 \
    --local-dir ~/models/cohere-transcribe-03-2026
```

Then update `MODEL_ID` in `transcriber_igpu.py` to match your path:

```python
MODEL_ID = "/home/yourname/models/cohere-transcribe-03-2026"
```

### 3. Quantize to INT4 (one-time, ~15 min)

The model is 2B parameters (~8 GB in FP32). We export it to OpenVINO and
compress weights to INT4, reducing iGPU memory usage from ~3.7 GB to ~1.4 GB:

```bash
./quantize.py
```

This exports and quantizes both the encoder (~1.1 GB) and decoder (~87 MB)
to `~/.cache/cohere-asr/openvino/`. Only needs to run once.

To force a re-export (e.g. after changing `MODEL_ID`):

```bash
./quantize.py --force
```

### 4. Run

```bash
./pirotalk_igpu.py
```

Wait for the tray icon to turn **green**, then hold **Pause** to dictate.

---

## Quick Start — NPU

```bash
./install.sh --npu
python3 pirotalk_npu.py
```

No quantization step needed — Whisper exports automatically on first run
(~30 seconds for the `base` model).

---

## How it works

```
Hold Pause → record from microphone
                  ↓
Release Pause → encoder runs on iGPU or NPU (~0.5s)
                  ↓
              decoder runs on iGPU or CPU (~0.2s)
                  ↓
              text pasted into the window that was focused
              when you started holding the key
```

You can freely switch windows while waiting — the text will always land in the app you were in when you pressed Pause.

A system tray icon shows the current state:

- **Grey** — loading model
- **Green** — ready
- **Red** — recording
- **Blue** — encoder running
- **Orange** — decoder running

---

## Configuration

Edit constants at the top of each file:

| File | Constant | Default | Description |
|---|---|---|---|
| `mic.py` | `HOTKEY_CODE` | `119` (Pause) | evdev keycode for hold-to-talk |
| `mic.py` | `MIC_DEVICE` | `FHD Camera Microphone` | Microphone name substring to match |
| `mic.py` | `AUTO_ENTER` | `False` | Press Enter automatically after each dictation |
| `transcriber_igpu.py` | `MODEL_ID` | *(your path)* | Path to CohereASR model |
| `transcriber_igpu.py` | `LANGUAGE` | `en` | Target language code |
| `transcriber_igpu.py` | `OV_DEVICE` | `GPU` | OpenVINO device (`GPU`, `CPU`) |
| `transcriber_npu.py` | `WHISPER_MODEL` | `base` | Whisper model size (`tiny`–`large`) |
| `transcriber_npu.py` | `LANGUAGE` | `en` | Target language (`None` = auto-detect) |

### Changing the hotkey

Run this to find the evdev keycode for any key on your keyboard:

```bash
python3 -c "
import evdev, selectors
devs = [evdev.InputDevice(p) for p in evdev.list_devices()]
sel = selectors.DefaultSelector()
for d in devs: sel.register(d, selectors.EVENT_READ)
print('Press the key you want to use...')
for key, _ in sel.select():
    for e in key.data.read():
        if e.type == evdev.ecodes.EV_KEY and e.value == 1:
            print(f'HOTKEY_CODE = {e.code}  # {evdev.ecodes.KEY[e.code]}')
            raise SystemExit
"
```

Then set `HOTKEY_CODE` and `HOTKEY_NAME` in `mic.py` to match.

---

## Architecture

```
mic.py              Shared orchestrator: GTK tray icon, state machine,
                    audio capture, evdev key listener.
                    VoiceTypeDaemon(transcriber_class) accepts any
                    transcriber with load() / encode() / decode().

pirotalk_igpu.py         Launcher: iGPU mode (CohereASR via OpenVINO)
pirotalk_npu.py          Launcher: NPU mode (Whisper via OpenVINO)

transcriber_igpu.py CohereASR: Parakeet encoder on iGPU, Cohere decoder
                    on iGPU. INT4 weight quantization via NNCF.
transcriber_npu.py  Whisper: encoder on Intel NPU, decoder on CPU.

typer.py            Text injection: sets GTK clipboard, pastes via
                    xdotool (Ctrl+Shift+V for terminals, Ctrl+V elsewhere).

quantize.py         One-time export script: downloads model, exports
                    encoder + decoder to OpenVINO INT4.
```

---

## Autostart

To have piroTalk start automatically on login:

```bash
./autostart.sh           # iGPU (default)
./autostart.sh --npu     # NPU
./autostart.sh --remove  # disable autostart
```

---

## Logs

```
~/.local/share/mic/pirotalk_igpu.log
~/.local/share/mic/pirotalk_npu.log
```

---

## License

MIT
