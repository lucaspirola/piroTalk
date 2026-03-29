"""Type text via GTK clipboard + xdotool paste on X11."""
import subprocess
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gdk, Gtk

# Window classes that use Ctrl+Shift+V to paste (terminal emulators)
_TERM_CLASSES = frozenset({
    "gnome-terminal", "xterm", "konsole", "xfce4-terminal",
    "terminator", "alacritty", "kitty", "st", "urxvt", "tilix",
    "lxterminal", "qterminal", "rxvt", "mate-terminal",
    "x-terminal-emulator",
})


def _paste_key():
    wid = subprocess.run(
        ["xdotool", "getactivewindow"],
        capture_output=True, text=True,
    ).stdout.strip()
    # xprop returns: WM_CLASS(STRING) = "instance", "ClassName"
    out = subprocess.run(
        ["xprop", "WM_CLASS", "-id", wid],
        capture_output=True, text=True,
    ).stdout
    wclass = out.split('"')[-2].lower() if '"' in out else ""
    return "ctrl+shift+v" if wclass in _TERM_CLASSES else "ctrl+v"


class Typer:
    def __init__(self):
        pass

    def type_text(self, text):
        if not text:
            return

        done = threading.Event()

        def _set_clipboard():
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)
            done.set()
            return False

        GLib.idle_add(_set_clipboard)
        done.wait(timeout=2.0)

        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", _paste_key()],
            check=False,
        )

    def close(self):
        pass
