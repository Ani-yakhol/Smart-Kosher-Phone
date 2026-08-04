#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SmartHomeEngine — שליטה ברכיבי בית חכם (כגון פיוז חכם בארון חשמל) שמחוברים
לקו טלפוני (GSM relay). התוכנה מתקשרת ל"קו הבית החכם" (המספר של רכיב
הבקרה), ולאחר מכן שולחת רצפי DTMF (הקשות) כדי לבחור רכיב ולהפעיל/לכבות
אותו או להעביר אותו למצב מסוים — בדיוק כפי שהיה עושה אדם שמתקשר ומקיש
בעצמו על מקשי הטלפון.

לכל רכיב ("מכשיר בית חכם") מוגדר:
  • key            — מקש (או רצף מקשים) שבוחר את הרכיב מתוך התפריט
  • on_seq/off_seq — רצף מקשים נוסף להפעלה/כיבוי
  • states         — רשימת מצבים נוספים מעבר להפעלה/כיבוי (שם + רצף מקשים)
  • nickname_audio — קובץ שמע (הקלטה) שמכריז את שם הרכיב והמקש שלו
"""

import json
import os
import time
import wave
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from PyQt6.QtCore import QObject, QTimer, pyqtSignal as Signal

SETTINGS_DIR = os.path.join(os.path.expanduser("~"), "BluePhone")
SMARTHOME_PATH = os.path.join(SETTINGS_DIR, "smart_home.json")
NICKNAMES_DIR = os.path.join(SETTINGS_DIR, "smart_home_nicknames")

# Minimum gap between DTMF digits sent to the relay, so the device has time
# to register each key press correctly (mirrors how a person would actually
# press keys one at a time, not instantaneously).
DTMF_GAP_MS = 350


@dataclass
class DeviceState:
    """מצב נוסף מעבר להפעלה/כיבוי הרגילים (למשל 'מצב חסכון')"""
    name: str
    key_sequence: str


@dataclass
class SmartHomeDevice:
    device_id: str
    name: str = ""
    key: str = ""                 # e.g. "1" or "12" — selects the device
    on_seq: str = ""               # e.g. "1" — sent after `key` to turn on
    off_seq: str = ""              # e.g. "2" — sent after `key` to turn off
    states: List[DeviceState] = field(default_factory=list)
    nickname_audio: str = ""       # path to a recorded announcement clip
    default_timed_minutes: int = 30
    enabled: bool = True

    def to_dict(self):
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: dict) -> "SmartHomeDevice":
        states = [DeviceState(**s) for s in d.get("states", [])]
        d = dict(d)
        d["states"] = states
        return SmartHomeDevice(**d)


@dataclass
class SmartHomeSettings:
    hub_number: str = ""
    hub_name: str = "בית חכם"
    devices: List[SmartHomeDevice] = field(default_factory=list)
    announce_on_connect: bool = False


def _load() -> dict:
    try:
        if os.path.exists(SMARTHOME_PATH):
            return json.loads(open(SMARTHOME_PATH, encoding="utf-8").read())
    except Exception:
        pass
    return {}


def _save(data: dict):
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    open(SMARTHOME_PATH, "w", encoding="utf-8").write(
        json.dumps(data, ensure_ascii=False, indent=2))


class SmartHomeEngine(QObject):
    """
    מנהל רכיבי הבית החכם — שולח רצפי DTMF, מנהל טיימרים לכיבוי אוטומטי,
    ומנגן הכרזות שמע.
    """

    status_changed       = Signal(str)
    sequence_progress    = Signal(str, str)   # device_id, description
    sequence_complete    = Signal(str, str)   # device_id, action ("on"/"off"/state name)
    timed_off_scheduled  = Signal(str, int)   # device_id, minutes
    timed_off_fired      = Signal(str)        # device_id
    devices_changed       = Signal()

    def __init__(self, bt_manager=None, language_manager=None, parent=None):
        super().__init__(parent)
        self.bt = bt_manager
        self.lang_mgr = language_manager
        self.settings = SmartHomeSettings()
        self._timed_off_timers: dict[str, QTimer] = {}
        self._player = None
        os.makedirs(NICKNAMES_DIR, exist_ok=True)
        self.load_settings()

    def _t(self, he: str, en: str) -> str:
        if self.lang_mgr is not None and not self.lang_mgr.is_rtl:
            return en
        return he

    # ── Persistence ──────────────────────────────────────

    def load_settings(self):
        data = _load()
        self.settings.hub_number = data.get("hub_number", "")
        self.settings.hub_name = data.get("hub_name", self._t("בית חכם", "Smart Home"))
        self.settings.announce_on_connect = data.get("announce_on_connect", False)
        self.settings.devices = [
            SmartHomeDevice.from_dict(d) for d in data.get("devices", [])
        ]

    def save_settings(self):
        data = {
            "hub_number": self.settings.hub_number,
            "hub_name": self.settings.hub_name,
            "announce_on_connect": self.settings.announce_on_connect,
            "devices": [d.to_dict() for d in self.settings.devices],
        }
        _save(data)
        self.devices_changed.emit()

    # ── Device management ────────────────────────────────

    def add_device(self, device: SmartHomeDevice):
        self.settings.devices.append(device)
        self.save_settings()

    def update_device(self, device: SmartHomeDevice):
        for i, d in enumerate(self.settings.devices):
            if d.device_id == device.device_id:
                self.settings.devices[i] = device
                break
        self.save_settings()

    def remove_device(self, device_id: str):
        self.settings.devices = [d for d in self.settings.devices if d.device_id != device_id]
        self._cancel_timed_off(device_id)
        self.save_settings()

    def get_device(self, device_id: str) -> Optional[SmartHomeDevice]:
        return next((d for d in self.settings.devices if d.device_id == device_id), None)

    # ── DTMF sequence sending ────────────────────────────

    def send_sequence(self, device_id: str, seq: str, action_label: str = ""):
        """
        שלח רצף מקשים לרכיב מסוים: קודם ה-key שבוחר את הרכיב, ואז את
        רצף הפעולה (on_seq/off_seq/מצב מותאם). ההקשות נשלחות אחת אחרי
        השנייה עם השהייה קצרה ביניהן, בדיוק כמו הקשה אנושית אמיתית.
        """
        device = self.get_device(device_id)
        if not device:
            return False
        if not self.bt or not self.bt.is_connected:
            self.status_changed.emit(self._t(
                "לא מחובר לפלאפון — לא ניתן לשלוח הקשות", "Not connected to a phone — can't send key presses"))
            return False

        full_seq = (device.key or "") + (seq or "")
        if not full_seq:
            return False

        digits = list(full_seq)
        self.sequence_progress.emit(device_id, self._t(
            f"שולח הקשות ל-{device.name}: {full_seq}", f"Sending key presses to {device.name}: {full_seq}"))

        def send_next(index=0):
            if index >= len(digits):
                self.sequence_complete.emit(device_id, action_label)
                return
            self.bt.send_dtmf(digits[index])
            QTimer.singleShot(DTMF_GAP_MS, lambda: send_next(index + 1))

        send_next()
        return True

    def turn_on(self, device_id: str):
        device = self.get_device(device_id)
        if device:
            self.send_sequence(device_id, device.on_seq, self._t("הפעלה", "On"))
            self._cancel_timed_off(device_id)

    def turn_off(self, device_id: str):
        device = self.get_device(device_id)
        if device:
            self.send_sequence(device_id, device.off_seq, self._t("כיבוי", "Off"))
            self._cancel_timed_off(device_id)

    def set_state(self, device_id: str, state: DeviceState):
        self.send_sequence(device_id, state.key_sequence, state.name)

    # ── Timed activation ─────────────────────────────────

    def turn_on_timed(self, device_id: str, minutes: int):
        """
        הפעל את הרכיב, ותזמן כיבוי אוטומטי אחרי מספר הדקות שנקבע.
        הכיבוי מתבצע ע"י שליחת רצף הכיבוי דרך אותה שיחה (אם היא עדיין
        פעילה) — בדיוק כפי שהיה עושה מי שמתקשר שוב כדי לכבות.
        """
        device = self.get_device(device_id)
        if not device:
            return
        self.turn_on(device_id)
        self._cancel_timed_off(device_id)

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._fire_timed_off(device_id))
        timer.start(minutes * 60 * 1000)
        self._timed_off_timers[device_id] = timer
        self.timed_off_scheduled.emit(device_id, minutes)
        self.status_changed.emit(self._t(
            f"{device.name}: יופעל כעת ויכובה אוטומטית בעוד {minutes} דקות",
            f"{device.name}: turning on now, will auto-off in {minutes} minutes"))

    def _fire_timed_off(self, device_id: str):
        device = self.get_device(device_id)
        if not device:
            return
        if self.bt and self.bt.is_connected:
            # Same call still active — just send the off sequence.
            self.send_sequence(device_id, device.off_seq, self._t("כיבוי אוטומטי", "Auto-off"))
        else:
            # Call ended in the meantime — redial the hub then send off.
            self.status_changed.emit(self._t(
                f"מתקשר מחדש ל{self.settings.hub_name} לכיבוי אוטומטי של {device.name}",
                f"Redialing {self.settings.hub_name} to auto-off {device.name}"))
            if self.bt:
                self.bt.dial(self.settings.hub_number)
                QTimer.singleShot(4000, lambda: self.send_sequence(
                    device_id, device.off_seq, self._t("כיבוי אוטומטי", "Auto-off")))
        self.timed_off_fired.emit(device_id)
        self._timed_off_timers.pop(device_id, None)

    def _cancel_timed_off(self, device_id: str):
        timer = self._timed_off_timers.pop(device_id, None)
        if timer:
            timer.stop()

    def remaining_timed_seconds(self, device_id: str) -> Optional[int]:
        timer = self._timed_off_timers.get(device_id)
        if timer and timer.isActive():
            return max(0, timer.remainingTime() // 1000)
        return None

    # ── Nickname audio (record / play) ───────────────────

    def nickname_path(self, device_id: str) -> str:
        return os.path.join(NICKNAMES_DIR, f"{device_id}.wav")

    def record_nickname(self, device_id: str, duration: float = 3.0, callback=None):
        """הקלט הכרזה קולית קצרה לרכיב (למשל: 'תנור סלון, מקש 5')"""
        try:
            import sounddevice as sd
        except ImportError:
            if callback:
                callback(False, self._t("sounddevice לא מותקן", "sounddevice not installed"))
            return

        path = self.nickname_path(device_id)
        samplerate = 44100

        def _record():
            try:
                audio = sd.rec(int(duration * samplerate), samplerate=samplerate,
                               channels=1, dtype='int16')
                sd.wait()
                with wave.open(path, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(samplerate)
                    wf.writeframes(audio.tobytes())
                if callback:
                    callback(True, path)
            except Exception as e:
                if callback:
                    callback(False, str(e))

        import threading
        threading.Thread(target=_record, daemon=True).start()

    def play_nickname(self, device_id: str):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        path = self.nickname_path(device_id)
        if not os.path.exists(path):
            return False
        if not self._player:
            self._audio_out = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio_out)
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()
        return True

    def announce_all(self):
        """נגן את כל ההכרזות של הרכיבים ברצף, כדי ללמוד את מיפוי המקשים"""
        devices = [d for d in self.settings.devices if os.path.exists(self.nickname_path(d.device_id))]
        if not devices:
            self.status_changed.emit(self._t("אין הכרזות מוקלטות", "No recorded announcements"))
            return

        def play_next(index=0):
            if index >= len(devices):
                return
            self.play_nickname(devices[index].device_id)
            # Rough estimate: wait 3.5s between clips (typical short clip length)
            QTimer.singleShot(3500, lambda: play_next(index + 1))

        play_next()
