#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TextModem - מודם טקסט דרך שיחה טלפונית
מקודד טקסט לרצף DTMF ומפענח בצד השני.

פרוטוקול:
  - כל תו מקודד ל-2 ספרות DTMF (בסיס-16)
  - תדירות: 65ms לספרה, 35ms pause (סה"כ ~200ms לתו)
  - תחילת הודעה:  ##99  (אות sync)
  - סוף הודעה:    ##00  (אות end)
  - "כותב":       ##11  (typing indicator — start)
  - "סיים":       ##12  (typing indicator — stop)
  - נקרא:         ##22  (read receipt)

מפת קידוד:
  תווים עבריים א-ת  → 00-26  (27 אותיות)
  ספרות 0-9         → 30-39
  רווח               → 40
  . , ! ? : -        → 41-46
  newline            → 47
  A-Z               → 50-75
  a-z               → 80-05  (wraps)
"""

import time
import threading
import queue
from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal as Signal


# ── Character table ───────────────────────────────────────

HEBREW_LETTERS = "אבגדהוזחטיכלמנסעפצקרשת"
HEBREW_FINALS  = "ךםןףץ"   # final forms → same as regular

# Build encode/decode tables
_ENCODE: dict[str, str] = {}
_DECODE: dict[str, str] = {}

def _add(char: str, code: int):
    code_str = f"{code:02d}"
    _ENCODE[char] = code_str
    _DECODE[code_str] = char

# Hebrew letters 00-21
for _i, _c in enumerate(HEBREW_LETTERS):
    _add(_c, _i)
# Final forms → same code as base
for _fc, _bc in zip(HEBREW_FINALS, "כמנפצ"):
    _ENCODE[_fc] = _ENCODE[_bc]

# Digits 30-39
for _i, _d in enumerate("0123456789"):
    _add(_d, 30 + _i)

# Common chars
_add(" ",  40)
_add(".",  41)
_add(",",  42)
_add("!",  43)
_add("?",  44)
_add(":",  45)
_add("-",  46)
_add("\n", 47)
_add('"',  48)
_add("'",  49)

# Latin uppercase A-Z → 50-75
for _i, _c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _add(_c, 50 + _i)

# Latin lowercase a-z → 76-101 (use 3-digit? no — keep 2 digit → wrap mod 100)
for _i, _c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    code = (76 + _i) % 100
    _ENCODE[_c] = f"{code:02d}"
    _DECODE[f"{code:02d}"] = _c

# Control sequences (escape: ## prefix)
CTRL_START   = "##99"   # start of message
CTRL_END     = "##00"   # end of message
CTRL_TYPING  = "##11"   # typing started
CTRL_STOP_TY = "##12"   # typing stopped
CTRL_READ    = "##22"   # read receipt

# DTMF timing (milliseconds)
TONE_MS   = 70    # tone on duration
PAUSE_MS  = 40    # inter-tone gap
CHAR_GAP  = 80    # extra gap between characters


def encode_text(text: str) -> list[str]:
    """המר טקסט לרצף ספרות DTMF"""
    digits = []
    for char in text:
        code = _ENCODE.get(char)
        if code is None:
            continue  # skip unknown characters
        digits.append(code[0])
        digits.append(code[1])
    return digits


def decode_digits(digits: str) -> str:
    """המר רצף ספרות DTMF לטקסט"""
    text = []
    i = 0
    while i + 1 < len(digits):
        code = digits[i:i+2]
        char = _DECODE.get(code)
        if char is not None:
            text.append(char)
        i += 2
    return "".join(text)


# ── TextModem class ───────────────────────────────────────

class TextModem(QObject):
    """
    מודם טקסט דו-כיווני דרך DTMF
    שולח: encode_text → send_dtmf sequence via BluetoothManager
    מקבל: מאזין ל-DTMF incoming → decode → emit message
    """
    message_received   = Signal(str, str)  # (number, text)
    typing_started     = Signal(str)        # number
    typing_stopped     = Signal(str)        # number
    read_receipt       = Signal(str)        # number
    send_progress      = Signal(int, int)   # (sent_chars, total_chars)
    send_complete      = Signal()
    error_occurred     = Signal(str)

    def __init__(self, bt_manager=None, language_manager=None, parent=None):
        super().__init__(parent)
        self.bt = bt_manager
        self.lang_mgr = language_manager
        self._recv_buffer: dict[str, str] = {}   # number → raw digit string
        self._recv_in_msg: dict[str, bool] = {}  # number → inside message?
        self._send_queue: queue.Queue = queue.Queue()
        self._send_thread: Optional[threading.Thread] = None
        self._sending = False

    def _t(self, he: str, en: str) -> str:
        if self.lang_mgr is not None and not self.lang_mgr.is_rtl:
            return en
        return he

    # ── Sending ───────────────────────────────────────────

    def send_message(self, text: str):
        """שלח הודעת טקסט — מקדד ושולח ב-thread"""
        if not self.bt:
            self.error_occurred.emit(self._t("לא מחובר לפלאפון", "Not connected to a phone"))
            return
        self._send_queue.put(("message", text))
        if not self._sending:
            self._start_send_thread()

    def send_typing_start(self):
        if self.bt:
            self._send_sequence(list(CTRL_TYPING))

    def send_typing_stop(self):
        if self.bt:
            self._send_sequence(list(CTRL_STOP_TY))

    def send_read_receipt(self):
        if self.bt:
            self._send_sequence(list(CTRL_READ))

    def _start_send_thread(self):
        self._sending = True
        self._send_thread = threading.Thread(
            target=self._send_worker, daemon=True)
        self._send_thread.start()

    def _send_worker(self):
        while not self._send_queue.empty():
            try:
                kind, data = self._send_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "message":
                self._send_full_message(data)
        self._sending = False

    def _send_full_message(self, text: str):
        # START marker
        self._send_sequence(list(CTRL_START))
        time.sleep(CHAR_GAP / 1000)

        # Encode and send
        digits = encode_text(text)
        total_chars = len(text)
        sent = 0

        for i in range(0, len(digits), 2):
            pair = digits[i:i+2]
            self._send_sequence(pair)
            sent += 1
            self.send_progress.emit(sent, total_chars)
            time.sleep(CHAR_GAP / 1000)

        # END marker
        time.sleep(CHAR_GAP / 1000)
        self._send_sequence(list(CTRL_END))
        self.send_complete.emit()

    def _send_sequence(self, digits: list[str]):
        """שלח רצף ספרות DTMF"""
        for d in digits:
            if d == "#":
                self.bt.send_dtmf("#")
            elif d == "*":
                self.bt.send_dtmf("*")
            elif d in "0123456789":
                self.bt.send_dtmf(d)
            time.sleep((TONE_MS + PAUSE_MS) / 1000)

    # ── Receiving ─────────────────────────────────────────

    def on_dtmf_received(self, caller_number: str, digit: str):
        """
        קרא ע"י BluetoothManager כשמגיע DTMF מהצד השני.
        digit: "0"-"9", "*", "#"
        """
        buf = self._recv_buffer.get(caller_number, "")
        buf += digit
        self._recv_buffer[caller_number] = buf

        # Check for control sequences
        if buf.endswith(CTRL_START.replace("#", "")):
            # Strip the ctrl start, begin message
            self._recv_buffer[caller_number] = ""
            self._recv_in_msg[caller_number] = True
            return

        if buf.endswith("0099"):  # CTRL_START (## = treated as 00 in digit stream? No)
            pass

        # Simpler: look for known ctrl patterns in full buffer
        self._check_ctrl(caller_number)

    def _check_ctrl(self, number: str):
        buf = self._recv_buffer.get(number, "")

        # Start marker detection: digits 9,9 after flush
        if buf.endswith("99") and not self._recv_in_msg.get(number):
            self._recv_buffer[number] = ""
            self._recv_in_msg[number] = True
            return

        # End marker: digits 0,0 while in message
        if buf.endswith("00") and self._recv_in_msg.get(number):
            # Decode everything before the final 00
            payload = buf[:-2]
            self._recv_in_msg[number] = False
            self._recv_buffer[number] = ""
            text = decode_digits(payload)
            if text:
                self.message_received.emit(number, text)
            return

        # Typing start: 11
        if buf.endswith("11"):
            self._recv_buffer[number] = ""
            self.typing_started.emit(number)
            return

        # Typing stop: 12
        if buf.endswith("12"):
            self._recv_buffer[number] = ""
            self.typing_stopped.emit(number)
            return

        # Read receipt: 22
        if buf.endswith("22"):
            self._recv_buffer[number] = ""
            self.read_receipt.emit(number)
            return

        # Prevent buffer overflow
        if len(buf) > 2000:
            self._recv_buffer[number] = buf[-500:]
