"""Type text via evdev UInput using Dvorak-intl layout keycodes."""

import time
from evdev import UInput, ecodes

# Dvorak: character -> (evdev_keycode, needs_shift)
DVORAK_MAP = {
    'a': (ecodes.KEY_A, False),
    'b': (ecodes.KEY_N, False),
    'c': (ecodes.KEY_I, False),
    'd': (ecodes.KEY_H, False),
    'e': (ecodes.KEY_D, False),
    'f': (ecodes.KEY_Y, False),
    'g': (ecodes.KEY_U, False),
    'h': (ecodes.KEY_J, False),
    'i': (ecodes.KEY_G, False),
    'j': (ecodes.KEY_C, False),
    'k': (ecodes.KEY_V, False),
    'l': (ecodes.KEY_P, False),
    'm': (ecodes.KEY_M, False),
    'n': (ecodes.KEY_L, False),
    'o': (ecodes.KEY_S, False),
    'p': (ecodes.KEY_R, False),
    'q': (ecodes.KEY_X, False),
    'r': (ecodes.KEY_O, False),
    's': (ecodes.KEY_SEMICOLON, False),
    't': (ecodes.KEY_K, False),
    'u': (ecodes.KEY_F, False),
    'v': (ecodes.KEY_DOT, False),
    'w': (ecodes.KEY_COMMA, False),
    'x': (ecodes.KEY_B, False),
    'y': (ecodes.KEY_T, False),
    'z': (ecodes.KEY_SLASH, False),
    ' ': (ecodes.KEY_SPACE, False),
    '.': (ecodes.KEY_E, False),
    ',': (ecodes.KEY_W, False),
    "'": (ecodes.KEY_Q, False),
    ';': (ecodes.KEY_Z, False),
    '/': (ecodes.KEY_LEFTBRACE, False),
    '-': (ecodes.KEY_APOSTROPHE, False),
    '=': (ecodes.KEY_RIGHTBRACE, False),
    '[': (ecodes.KEY_MINUS, False),
    ']': (ecodes.KEY_EQUAL, False),
    '\n': (ecodes.KEY_ENTER, False),
    'A': (ecodes.KEY_A, True),
    'B': (ecodes.KEY_N, True),
    'C': (ecodes.KEY_I, True),
    'D': (ecodes.KEY_H, True),
    'E': (ecodes.KEY_D, True),
    'F': (ecodes.KEY_Y, True),
    'G': (ecodes.KEY_U, True),
    'H': (ecodes.KEY_J, True),
    'I': (ecodes.KEY_G, True),
    'J': (ecodes.KEY_C, True),
    'K': (ecodes.KEY_V, True),
    'L': (ecodes.KEY_P, True),
    'M': (ecodes.KEY_M, True),
    'N': (ecodes.KEY_L, True),
    'O': (ecodes.KEY_S, True),
    'P': (ecodes.KEY_R, True),
    'Q': (ecodes.KEY_X, True),
    'R': (ecodes.KEY_O, True),
    'S': (ecodes.KEY_SEMICOLON, True),
    'T': (ecodes.KEY_K, True),
    'U': (ecodes.KEY_F, True),
    'V': (ecodes.KEY_DOT, True),
    'W': (ecodes.KEY_COMMA, True),
    'X': (ecodes.KEY_B, True),
    'Y': (ecodes.KEY_T, True),
    'Z': (ecodes.KEY_SLASH, True),
    '!': (ecodes.KEY_1, True),
    '@': (ecodes.KEY_2, True),
    '#': (ecodes.KEY_3, True),
    '$': (ecodes.KEY_4, True),
    '%': (ecodes.KEY_5, True),
    '^': (ecodes.KEY_6, True),
    '&': (ecodes.KEY_7, True),
    '*': (ecodes.KEY_8, True),
    '(': (ecodes.KEY_9, True),
    ')': (ecodes.KEY_0, True),
    '?': (ecodes.KEY_LEFTBRACE, True),
    '"': (ecodes.KEY_Q, True),
    ':': (ecodes.KEY_Z, True),
    '0': (ecodes.KEY_0, False),
    '1': (ecodes.KEY_1, False),
    '2': (ecodes.KEY_2, False),
    '3': (ecodes.KEY_3, False),
    '4': (ecodes.KEY_4, False),
    '5': (ecodes.KEY_5, False),
    '6': (ecodes.KEY_6, False),
    '7': (ecodes.KEY_7, False),
    '8': (ecodes.KEY_8, False),
    '9': (ecodes.KEY_9, False),
}


class Typer:
    """Virtual keyboard that types text via evdev UInput."""

    def __init__(self):
        all_keys = set(k for k, _ in DVORAK_MAP.values())
        all_keys.add(ecodes.KEY_LEFTSHIFT)
        cap = {ecodes.EV_KEY: list(all_keys)}
        self.ui = UInput(cap, name="mic-voice-to-type",
                         vendor=0x1, product=0x1, version=0x1)
        time.sleep(0.3)

    def type_text(self, text):
        """Type a string into the focused window."""
        for ch in text:
            mapping = DVORAK_MAP.get(ch)
            if mapping is None:
                continue
            keycode, shift = mapping
            if shift:
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
                self.ui.syn()
            self.ui.write(ecodes.EV_KEY, keycode, 1)
            self.ui.syn()
            self.ui.write(ecodes.EV_KEY, keycode, 0)
            self.ui.syn()
            if shift:
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
                self.ui.syn()

    def close(self):
        self.ui.close()
