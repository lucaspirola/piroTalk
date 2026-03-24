# mic - NPU Voice-to-Type for Linux

Hold a key, speak, release — your words appear wherever your cursor is. Speech recognition runs on the Intel NPU via OpenVINO, keeping your CPU and GPU free.

Supports **100 languages** with automatic translation to English — speak in any language and get English text output. Or set it to transcribe in the original language.

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

**Quick install** (installs dependencies, sets permissions, enables autostart):

```bash
git clone https://github.com/lucaspirola/mic.git
cd mic
./install.sh
```

**Log out and back in** after install for group changes to take effect.

**Manual install** if you prefer:

```bash
# System packages
sudo apt-get install -y ffmpeg libportaudio2 gir1.2-ayatanaappindicator3-0.1

# Python packages
pip install --break-system-packages sounddevice evdev openai-whisper openvino torch numpy PyGObject

# Permissions
sudo usermod -aG input $USER
echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo chmod 0666 /dev/uinput
```

## Usage

```bash
python3 mic.py
```

1. Wait for the tray icon to turn **green**
2. Hold **Pause** key and speak
3. Release — transcribed text appears at your cursor

The daemon auto-starts on login after running `install.sh`. Logs are written to `~/.local/share/mic/mic.log`.

## Configuration

Edit the constants at the top of each file:

| File | Constant | Default | Description |
|---|---|---|---|
| `mic.py` | `HOTKEY_CODE` | `119` (Pause) | evdev keycode for the hold-to-talk key |
| `mic.py` | `MIC_DEVICE` | `FHD Camera Microphone` | Microphone name substring |
| `transcriber.py` | `WHISPER_MODEL` | `base` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large`) |
| `transcriber.py` | `LANGUAGE` | `en` | Target language code — forces translation to that language. Set to `None` to auto-detect and transcribe in the original language |
| `typer.py` | `DVORAK_MAP` | Dvorak-intl | Keyboard layout character-to-keycode map |

## Supported languages

100 languages with automatic translation. Speak in any of these and get text output in your configured target language:

Afrikaans, Amharic, Arabic, Assamese, Azerbaijani, Bashkir, Belarusian, Bulgarian, Bengali, Tibetan, Breton, Bosnian, Catalan, Czech, Welsh, Danish, German, Greek, English, Spanish, Estonian, Basque, Persian, Finnish, Faroese, French, Galician, Gujarati, Hausa, Hawaiian, Hebrew, Hindi, Croatian, Haitian Creole, Hungarian, Armenian, Indonesian, Icelandic, Italian, Japanese, Javanese, Georgian, Kazakh, Khmer, Kannada, Korean, Latin, Luxembourgish, Lingala, Lao, Lithuanian, Latvian, Malagasy, Maori, Macedonian, Malayalam, Mongolian, Marathi, Malay, Maltese, Myanmar, Nepali, Dutch, Nynorsk, Norwegian, Occitan, Punjabi, Polish, Pashto, Portuguese, Romanian, Russian, Sanskrit, Sindhi, Sinhala, Slovak, Slovenian, Shona, Somali, Albanian, Serbian, Sundanese, Swedish, Swahili, Tamil, Telugu, Tajik, Thai, Turkmen, Tagalog, Turkish, Tatar, Ukrainian, Urdu, Uzbek, Vietnamese, Yiddish, Yoruba, Cantonese, Chinese.

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
