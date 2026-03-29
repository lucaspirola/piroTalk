"""Type text via GTK clipboard + paste keystroke (X11 and Wayland)."""
import os
import subprocess
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gdk, Gtk

_IS_WAYLAND = bool(os.environ.get("WAYLAND_DISPLAY"))

# Window classes that use Ctrl+Shift+V to paste (terminal emulators)
_TERM_CLASSES = frozenset({
    "gnome-terminal", "xterm", "konsole", "xfce4-terminal",
    "terminator", "alacritty", "kitty", "st", "urxvt", "tilix",
    "lxterminal", "qterminal", "rxvt", "mate-terminal",
    "x-terminal-emulator",
})


def _paste_cmd():
    """Return the command to send a paste keystroke to the focused window."""
    # Try xdotool — works on X11 and for XWayland apps on Wayland
    wid = subprocess.run(
        ["xdotool", "getactivewindow"],
        capture_output=True, text=True,
    )
    if wid.returncode == 0 and wid.stdout.strip():
        # X11 or XWayland: detect terminal class and choose the right shortcut
        out = subprocess.run(
            ["xprop", "WM_CLASS", "-id", wid.stdout.strip()],
            capture_output=True, text=True,
        ).stdout
        wclass = out.split('"')[-2].lower() if '"' in out else ""
        key = "ctrl+shift+v" if wclass in _TERM_CLASSES else "ctrl+v"
        return ["xdotool", "key", "--clearmodifiers", key]

    # Native Wayland window: fall back to wtype
    return ["wtype", "-k", "ctrl+v"]


class Typer:
    def __init__(self):
        pass

    def type_text(self, text, window_id=None):
        if not text:
            return

        done = threading.Event()

        def _set_clipboard():
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)
            done.set()
            return False

        GLib.idle_add(_set_clipboard)
        done.wait(timeout=2.0)

        if window_id:
            subprocess.run(["xdotool", "windowfocus", "--sync", window_id], check=False)

        subprocess.run(_paste_cmd(), check=False)

    def send_enter(self):
        cmd = _paste_cmd()
        subprocess.run(cmd[:-1] + ["Return"], check=False)

    def close(self):
        pass
