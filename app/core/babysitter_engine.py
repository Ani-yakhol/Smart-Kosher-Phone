#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BabysitterEngine — מנוע בייביסיטר
זיהוי קול/בכי דרך מיקרופון + חיוג אוטומטי
"""

import threading
import time
import wave
import struct
import math
import os
import json
from dataclasses import dataclass, field
from typing import Optional, List, Callable
from PyQt6.QtCore import QObject, pyqtSignal as Signal, QTimer


# ── Extension settings ────────────────────────────────────

@dataclass
class BabysitterExtension:
    """שלוחה — חדר מנוטר"""
    ext_id: str
    name: str                       # "חדר תינוק", "סלון"
    mic_index: Optional[int] = None # None = ברירת מחדל
    enabled: bool = True


@dataclass
class BabysitterSettings:
    enabled: bool = False
    extensions: List[BabysitterExtension] = field(default_factory=list)
    call_numbers: List[str] = field(default_factory=list)  # מספרים לחייג
    alert_file: str = ""                    # קובץ WAV להשמעה בשיחה
    sensitivity: float = 0.35              # 0.0-1.0 (גבוה = רגיש יותר)
    silence_gap_sec: float = 3.0           # שתיקה לפני התראה
    min_sound_duration_sec: float = 1.5    # משך קול מינימלי לפני התראה
    auto_answer: bool = True               # ענה אוטומטית לחיוג ממספרים מורשים
    allowed_callers: List[str] = field(default_factory=list)
    monitor_mode: str = "both"             # "cry" | "voice" | "both"
    ring_timeout_sec: int = 20             # זמן המתנה לפני עבור למספר הבא


def _rms(data: bytes) -> float:
    """חשב RMS (עוצמת קול) ממאגר PCM 16-bit"""
    if not data or len(data) < 2:
        return 0.0
    count = len(data) // 2
    try:
        shorts = struct.unpack(f"{count}h", data[:count*2])
        rms = math.sqrt(sum(s*s for s in shorts) / count)
        return rms / 32768.0   # normalize 0-1
    except Exception:
        return 0.0


def _is_cry_pattern(rms_history: list, sensitivity: float) -> bool:
    """
    זיהוי תבנית בכי — RMS גבוה עם וריאציות (בכי = גלים).
    sensitivity 0-1: גבוה = מזהה אפילו קולות חלשים.
    """
    if len(rms_history) < 5:
        return False
    threshold = 0.04 + (1.0 - sensitivity) * 0.20
    recent = rms_history[-10:]
    loud_frames = sum(1 for r in recent if r > threshold)
    # לפחות 40% מהפריימים האחרונים מעל סף
    return loud_frames >= max(2, len(recent) * 0.4)


class SoundMonitor(QObject):
    """מאזין לקול ממיקרופון ומזהה תבניות"""
    sound_detected  = Signal(str, float)   # (ext_id, rms_level)
    silence_started = Signal(str)          # ext_id
    error_occurred  = Signal(str)

    def __init__(self, extension: BabysitterExtension,
                 settings: BabysitterSettings, language_manager=None, parent=None):
        super().__init__(parent)
        self.ext    = extension
        self.settings = settings
        self.lang_mgr = language_manager
        self._running  = False
        self._thread: Optional[threading.Thread] = None
        self._rms_history: list = []
        self._sound_start: Optional[float] = None
        self._last_sound_time = 0.0
        self._stop_event = threading.Event()

    def _t(self, he: str, en: str) -> str:
        if self.lang_mgr is not None and not self.lang_mgr.is_rtl:
            return en
        return he


    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop, daemon=True,
            name=f"BabyMonitor-{self.ext.ext_id}")
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_event.set()

    def _monitor_loop(self):
        RATE      = 16000
        CHUNK     = 1024
        try:
            import sounddevice as sd

            kwargs = {
                "samplerate": RATE,
                "channels": 1,
                "dtype": "int16",
                "blocksize": CHUNK,
            }
            if self.ext.mic_index is not None:
                kwargs["device"] = self.ext.mic_index

            with sd.RawInputStream(**kwargs) as stream:
                while self._running and not self._stop_event.is_set():
                    data, _ = stream.read(CHUNK)
                    rms = _rms(bytes(data))
                    self._rms_history.append(rms)
                    if len(self._rms_history) > 50:
                        self._rms_history.pop(0)

                    if _is_cry_pattern(self._rms_history,
                                        self.settings.sensitivity):
                        now = time.time()
                        if self._sound_start is None:
                            self._sound_start = now
                        elapsed = now - self._sound_start
                        if elapsed >= self.settings.min_sound_duration_sec:
                            self._last_sound_time = now
                            self.sound_detected.emit(self.ext.ext_id, rms)
                    else:
                        if self._sound_start is not None:
                            gap = time.time() - self._last_sound_time
                            if gap >= self.settings.silence_gap_sec:
                                self._sound_start = None
                                self.silence_started.emit(self.ext.ext_id)

        except ImportError:
            self.error_occurred.emit(self._t("sounddevice לא מותקן — pip install sounddevice", "sounddevice not installed — pip install sounddevice"))
        except Exception as e:
            self.error_occurred.emit(self._t(f"שגיאת מיקרופון: {e}", f"Microphone error: {e}"))


class BabysitterEngine(QObject):
    """
    מנוע בייביסיטר מלא:
    מניהל מספר שלוחות → מזהה קול/בכי → מחייג → משמיע התראה
    """
    alert_triggered     = Signal(str, str)   # (ext_id, ext_name)
    call_initiated      = Signal(str)        # number
    call_answered_auto  = Signal(str)        # number (auto-answer incoming)
    monitoring_started  = Signal()
    monitoring_stopped  = Signal()
    status_changed      = Signal(str)
    error_occurred      = Signal(str)

    # ── Recording buffer for playback ────────────────────
    recording_saved     = Signal(str)        # filepath

    def __init__(self, bt_manager=None, language_manager=None, parent=None):
        super().__init__(parent)
        self.bt = bt_manager
        self.lang_mgr = language_manager
        self.settings = BabysitterSettings()
        self._monitors: dict[str, SoundMonitor] = {}
        self._call_in_progress = False
        self._call_numbers_queue: list[str] = []
        self._current_number_idx = 0
        self._alert_timer = QTimer(self)
        self._alert_timer.setSingleShot(True)
        self._alert_timer.timeout.connect(self._try_next_number)
        self._last_alert_ext: Optional[str] = None
        self._cooldown_timer = QTimer(self)
        self._cooldown_timer.setSingleShot(True)
        self._cooldown = False
        self._cooldown_timer.timeout.connect(self._reset_cooldown)

        # Recording buffers per extension
        self._rec_buffers: dict[str, list] = {}
        self._is_recording: dict[str, bool] = {}

        self._settings_path = os.path.join(
            os.path.expanduser("~"), "BluePhone", "babysitter.json")
        self._load_settings()

    def _t(self, he: str, en: str) -> str:
        if self.lang_mgr is not None and not self.lang_mgr.is_rtl:
            return en
        return he

    # ── Settings ──────────────────────────────────────────

    def _load_settings(self):
        if not os.path.exists(self._settings_path):
            return
        try:
            data = json.loads(open(self._settings_path, encoding="utf-8").read())
            s = data.get("settings", {})
            self.settings.enabled           = s.get("enabled", False)
            self.settings.sensitivity       = s.get("sensitivity", 0.35)
            self.settings.silence_gap_sec   = s.get("silence_gap_sec", 3.0)
            self.settings.min_sound_duration_sec = s.get("min_sound_sec", 1.5)
            self.settings.auto_answer       = s.get("auto_answer", True)
            self.settings.monitor_mode      = s.get("monitor_mode", "both")
            self.settings.ring_timeout_sec  = s.get("ring_timeout_sec", 20)
            self.settings.alert_file        = s.get("alert_file", "")
            self.settings.call_numbers = data.get("call_numbers", [])
            self.settings.allowed_callers = data.get("allowed_callers", [])
            for e in data.get("extensions", []):
                ext = BabysitterExtension(
                    ext_id=e["ext_id"], name=e["name"],
                    mic_index=e.get("mic_index"), enabled=e.get("enabled", True))
                self.settings.extensions.append(ext)
        except Exception:
            pass

    def save_settings(self):
        import dataclasses
        data = {
            "settings": {
                "enabled":         self.settings.enabled,
                "sensitivity":     self.settings.sensitivity,
                "silence_gap_sec": self.settings.silence_gap_sec,
                "min_sound_sec":   self.settings.min_sound_duration_sec,
                "auto_answer":     self.settings.auto_answer,
                "monitor_mode":    self.settings.monitor_mode,
                "ring_timeout_sec":self.settings.ring_timeout_sec,
                "alert_file":      self.settings.alert_file,
            },
            "call_numbers":    self.settings.call_numbers,
            "allowed_callers": self.settings.allowed_callers,
            "extensions": [
                {"ext_id": e.ext_id, "name": e.name,
                 "mic_index": e.mic_index, "enabled": e.enabled}
                for e in self.settings.extensions
            ],
        }
        os.makedirs(os.path.dirname(self._settings_path), exist_ok=True)
        open(self._settings_path, "w", encoding="utf-8").write(
            json.dumps(data, ensure_ascii=False, indent=2))

    # ── Monitoring control ────────────────────────────────

    def start_monitoring(self):
        if not self.settings.extensions:
            # Add default extension if none configured
            self.settings.extensions.append(
                BabysitterExtension("ext1", self._t("חדר תינוק", "Baby Room")))
        for ext in self.settings.extensions:
            if ext.enabled:
                m = SoundMonitor(ext, self.settings, self.lang_mgr)
                m.sound_detected.connect(self._on_sound)
                m.error_occurred.connect(self.error_occurred)
                m.start()
                self._monitors[ext.ext_id] = m
        self.settings.enabled = True
        self.monitoring_started.emit()
        self.status_changed.emit(self._t("ניטור פעיל", "Monitoring active"))

    def stop_monitoring(self):
        for m in self._monitors.values():
            m.stop()
        self._monitors.clear()
        self.settings.enabled = False
        self.monitoring_stopped.emit()
        self.status_changed.emit(self._t("ניטור מופסק", "Monitoring stopped"))

    # ── Alert handling ────────────────────────────────────

    def _on_sound(self, ext_id: str, rms: float):
        if self._call_in_progress or self._cooldown:
            return
        ext = next((e for e in self.settings.extensions
                    if e.ext_id == ext_id), None)
        ext_name = ext.name if ext else ext_id
        self._last_alert_ext = ext_id
        self.alert_triggered.emit(ext_id, ext_name)
        self.status_changed.emit(self._t(f"קול זוהה: {ext_name}", f"Sound detected: {ext_name}"))
        self._start_call_sequence()

    def _start_call_sequence(self):
        if not self.settings.call_numbers:
            self.status_changed.emit(self._t("אין מספרים להתקשר", "No numbers to call"))
            return
        self._call_numbers_queue = list(self.settings.call_numbers)
        self._current_number_idx = 0
        self._call_in_progress = True
        self._dial_current()

    def _dial_current(self):
        if self._current_number_idx >= len(self._call_numbers_queue):
            self.status_changed.emit(self._t("כל המספרים ניסו — אין מענה", "All numbers tried — no answer"))
            self._call_in_progress = False
            self._start_cooldown(60)
            return
        number = self._call_numbers_queue[self._current_number_idx]
        if self.bt:
            self.bt.dial(number)
        self.call_initiated.emit(number)
        ext_name = ""
        if self._last_alert_ext:
            ext = next((e for e in self.settings.extensions
                        if e.ext_id == self._last_alert_ext), None)
            ext_name = f" ({ext.name})" if ext else ""
        self.status_changed.emit(self._t(f"מחייג: {number}{ext_name}", f"Dialing: {number}{ext_name}"))
        # Wait for answer or timeout
        self._alert_timer.start(self.settings.ring_timeout_sec * 1000)

    def _try_next_number(self):
        """עבר למספר הבא אם לא נענה"""
        self._current_number_idx += 1
        self._dial_current()

    def on_call_answered(self, number: str):
        """קרא כשהשיחה נענית"""
        self._alert_timer.stop()
        self.status_changed.emit(self._t(f"שיחה נענתה: {number}", f"Call answered: {number}"))
        # Play alert file if configured
        if self.settings.alert_file and os.path.exists(self.settings.alert_file):
            self._play_alert_file()

    def on_call_ended(self):
        self._call_in_progress = False
        self._start_cooldown(30)

    def _play_alert_file(self):
        """השמע קובץ התראה בשיחה"""
        try:
            import sounddevice as sd
            import soundfile as sf
            data, sr = sf.read(self.settings.alert_file)
            sd.play(data, sr)
        except Exception:
            pass

    def _start_cooldown(self, seconds: int):
        """קירור — אל תשלח התראה שוב ל-X שניות"""
        self._cooldown = True
        self._cooldown_timer.start(seconds * 1000)

    def _reset_cooldown(self):
        self._cooldown = False

    # ── Auto answer incoming (from allowed callers) ───────

    def should_auto_answer(self, number: str) -> bool:
        """האם לענות אוטומטית לשיחה נכנסת ממספר מורשה?"""
        if not self.settings.enabled or not self.settings.auto_answer:
            return False
        if not self.settings.allowed_callers:
            return True  # no restriction
        return any(number.endswith(n) or n in number
                   for n in self.settings.allowed_callers)

    # ── Extensions management ─────────────────────────────

    def add_extension(self, name: str,
                      mic_index: Optional[int] = None) -> BabysitterExtension:
        import uuid
        ext = BabysitterExtension(
            ext_id=str(uuid.uuid4())[:8],
            name=name, mic_index=mic_index)
        self.settings.extensions.append(ext)
        return ext

    def remove_extension(self, ext_id: str):
        if ext_id in self._monitors:
            self._monitors[ext_id].stop()
            del self._monitors[ext_id]
        self.settings.extensions = [
            e for e in self.settings.extensions if e.ext_id != ext_id]

    def get_available_microphones(self) -> list:
        mics = []
        try:
            import sounddevice as sd
            for i, d in enumerate(sd.query_devices()):
                if d['max_input_channels'] > 0:
                    mics.append((i, d['name']))
        except Exception:
            pass
        return mics
