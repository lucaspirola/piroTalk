"""
Voice-to-Type daemon.
Hold Pause key to dictate, transcribes audio, types into focused app.
"""

import logging
import os
import signal
import subprocess
import sys
import threading

import gi
import numpy as np
import sounddevice as sd

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import GLib, Gtk, AyatanaAppIndicator3

from typer import Typer

# --- Configuration ---
HOTKEY_NAME = "KEY_PAUSE"
HOTKEY_CODE = 119
SAMPLE_RATE = 16000
MIC_DEVICE = "FHD Camera Microphone"
AUTO_ENTER = False  # Set to True to press Enter automatically after each dictation
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

# --- State ---
LOADING = "loading"
READY = "ready"
RECORDING = "recording"
ENCODING = "encoding"
DECODING = "decoding"


class VoiceTypeDaemon:
    def __init__(self, transcriber_class):
        self.state = LOADING
        self.transcriber = transcriber_class()
        self.typer = Typer()
        self.audio_buffer = []
        self.stream = None
        self.mic_device_index = None
        self.indicator = None
        self._target_window = None
        self._find_mic()

    def _find_mic(self):
        """Find the microphone device index by name."""
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if MIC_DEVICE in d["name"] and d["max_input_channels"] > 0:
                self.mic_device_index = i
                return
        print(f"WARNING: '{MIC_DEVICE}' not found, using default input")

    def _set_state(self, new_state):
        """Update state and tray icon. Must be called via GLib.idle_add."""
        self.state = new_state
        icon_path = os.path.join(ICON_DIR, f"{new_state}.png")
        self.indicator.set_icon_full(icon_path, new_state)

    def set_state(self, new_state):
        """Thread-safe state update."""
        GLib.idle_add(self._set_state, new_state)

    # --- Audio capture ---

    def _audio_callback(self, indata, frames, time_info, status):
        self.audio_buffer.append(indata.copy())

    def start_recording(self):
        self.audio_buffer = []
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=self.mic_device_index,
            callback=self._audio_callback,
        )
        self.stream.start()
        self.set_state(RECORDING)

    def stop_recording(self):
        """Stop recording and return audio as numpy array."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if not self.audio_buffer:
            return None
        audio = np.concatenate(self.audio_buffer, axis=0).flatten()
        self.audio_buffer = []
        return audio

    # --- Transcription + typing ---

    def process_audio(self, audio, target_window=None):
        """Transcribe audio and type result. Runs in worker thread."""
        self.set_state(ENCODING)
        try:
            encoder_out = self.transcriber.encode(audio)
            self.set_state(DECODING)
            text = self.transcriber.decode(encoder_out)
            if text:
                print(f"[mic] \"{text}\"")
                self.typer.type_text(text, window_id=target_window)
                if AUTO_ENTER:
                    self.typer.send_enter()
        except Exception as e:
            print(f"[mic] Error: {e}")
        self.set_state(READY)

    # --- Key listener ---

    def key_listener(self):
        """Listen for Pause key press/release via evdev. Runs in thread."""
        import evdev
        import selectors
        from evdev import ecodes

        keyboards = []
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                caps = dev.capabilities(verbose=False)
                if ecodes.EV_KEY in caps and HOTKEY_CODE in caps[ecodes.EV_KEY]:
                    keyboards.append(dev)
                else:
                    dev.close()
            except (OSError, PermissionError):
                continue

        if not keyboards:
            print("ERROR: No keyboard with Pause key found")
            print("Make sure your user is in the 'input' group and re-login.")
            GLib.idle_add(Gtk.main_quit)
            return

        sel = selectors.DefaultSelector()
        for kbd in keyboards:
            sel.register(kbd, selectors.EVENT_READ, kbd)
            print(f"Listening on: {kbd.name} ({kbd.path})")

        while True:
            for key, mask in sel.select():
                kbd = key.data
                for event in kbd.read():
                    if event.type != ecodes.EV_KEY:
                        continue
                    if event.code != HOTKEY_CODE:
                        continue

                    if event.value == 1 and self.state == READY:
                        r = subprocess.run(["xdotool", "getactivewindow"],
                                           capture_output=True, text=True)
                        self._target_window = r.stdout.strip() if r.returncode == 0 else None
                        print("[mic] Recording...")
                        self.start_recording()
                    elif event.value == 0 and self.state == RECORDING:
                        audio = self.stop_recording()
                        if audio is not None and len(audio) > SAMPLE_RATE * 0.3:
                            threading.Thread(target=self.process_audio,
                                             args=(audio, self._target_window),
                                             daemon=True).start()
                        else:
                            self.set_state(READY)

    # --- Tray icon ---

    def build_tray(self):
        icon_path = os.path.join(ICON_DIR, "loading.png")
        self.indicator = AyatanaAppIndicator3.Indicator.new(
            "mic-voice-to-type",
            icon_path,
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _: Gtk.main_quit())
        menu.append(quit_item)
        menu.show_all()
        self.indicator.set_menu(menu)

    # --- Startup ---

    def load_model_async(self):
        """Load model in background thread, then transition to READY."""
        def _load():
            self.transcriber.load()
            self.set_state(READY)

        threading.Thread(target=_load, daemon=True).start()

    def run(self):
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        self.build_tray()

        # Start key listener first so it's ready when model finishes loading
        key_thread = threading.Thread(target=self.key_listener, daemon=True)
        key_thread.start()

        self.load_model_async()

        print(f"Voice-to-type daemon started. Hold {HOTKEY_NAME} to dictate.")
        try:
            Gtk.main()
        except KeyboardInterrupt:
            pass


def setup_logging(name="mic"):
    """Configure logging to file and stderr."""
    log_dir = os.path.expanduser("~/.local/share/mic")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{name}.log")

    real_stderr = sys.stderr

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(real_stderr),
        ],
    )

    class LogWriter:
        def __init__(self, level):
            self.level = level
            self.buf = ""
        def write(self, msg):
            self.buf += msg
            while "\n" in self.buf:
                line, self.buf = self.buf.split("\n", 1)
                if line.strip():
                    self.level(line)
        def flush(self):
            if self.buf.strip():
                self.level(self.buf.strip())
            self.buf = ""

    sys.stdout = LogWriter(logging.info)
    sys.stderr = LogWriter(logging.warning)


