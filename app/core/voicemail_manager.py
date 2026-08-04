#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoicemailManager - ניהול תא קולי
מענה אוטומטי, זיהוי שתיקה, הודעות מותאמות אישית
"""

import os
import re
import time
import wave
import struct
import threading
import datetime
import json
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal as Signal, QTimer


@dataclass
class VoicemailRule:
    """כלל מענה תא קולי"""
    rule_id: str
    name: str
    enabled: bool = True
    # מתי לענות
    answer_always: bool = False
    answer_numbers: list = field(default_factory=list)   # מספרים ספציפיים
    answer_days: list = field(default_factory=list)      # 0=ראשון..6=שבת
    answer_hour_from: int = 0
    answer_hour_to: int = 23
    rings_before_answer: int = 3
    # הודעות
    greeting_file: str = ""       # נתיב לקובץ WAV
    greeting_text: str = "שלום, אינכם יכולים להשיג אותנו כרגע. אנא השאירו הודעה לאחר הצפצוף."
    goodbye_file: str = ""
    goodbye_text: str = "תודה רבה, שלום ולהתראות."
    # הגדרות
    max_message_sec: int = 120
    silence_cutoff_sec: int = 5
    play_goodbye: bool = True


class VoicemailManager(QObject):
    """מנהל תא קולי"""

    vm_answering       = Signal(str)   # number
    vm_greeting_done   = Signal()
    vm_recording       = Signal()
    vm_message_saved   = Signal(str)   # filepath
    vm_call_ended      = Signal()
    vm_state_changed   = Signal(str)   # state description

    def __init__(self, voicemail_dir: str = None,
                 recording_manager=None, bt_manager=None,
                 language_manager=None, parent=None):
        super().__init__(parent)
        self.rec_mgr = recording_manager
        self.bt_mgr  = bt_manager
        self.lang_mgr = language_manager

        self.vm_dir = Path(voicemail_dir or os.path.join(
            os.path.expanduser("~"), "BluePhone", "voicemail"))
        self.vm_dir.mkdir(parents=True, exist_ok=True)
        self.greetings_dir = self.vm_dir / "greetings"
        self.greetings_dir.mkdir(exist_ok=True)

        self._rules_path = self.vm_dir / "rules.json"
        self._rules: list[VoicemailRule] = []
        self._load_rules()
        if not self._rules:
            self._create_default_rule()

        # State
        self._active = False
        self._state = "idle"        # idle / waiting / greeting / recording / goodbye
        self._current_number = ""
        self._current_rule: Optional[VoicemailRule] = None
        self._silence_timer = QTimer(self)
        self._silence_timer.timeout.connect(self._on_silence_timeout)
        self._max_timer = QTimer(self)
        self._max_timer.timeout.connect(self._on_max_duration)
        self._ring_count = 0
        self._ring_timer = QTimer(self)
        self._ring_timer.timeout.connect(self._on_ring_tick)

    # ── Rules persistence ────────────────────────────────

    def _load_rules(self):
        if self._rules_path.exists():
            try:
                data = json.loads(self._rules_path.read_text(encoding="utf-8"))
                self._rules = [VoicemailRule(**d) for d in data]
            except Exception:
                self._rules = []

    def _save_rules(self):
        import dataclasses
        self._rules_path.write_text(
            json.dumps([dataclasses.asdict(r) for r in self._rules],
                       ensure_ascii=False, indent=2),
            encoding="utf-8")

    def _t(self, he: str, en: str) -> str:
        if self.lang_mgr is not None and not self.lang_mgr.is_rtl:
            return en
        return he

    def _create_default_rule(self):
        rule = VoicemailRule(
            rule_id="default",
            name=self._t("כלל ברירת מחדל", "Default Rule"),
            enabled=False,
            answer_always=True,
            rings_before_answer=4,
            greeting_text=self._t(
                "שלום, אינכם יכולים להשיג אותנו כרגע. "
                "אנא השאירו הודעה לאחר הצפצוף ונחזור אליכם בהקדם.",
                "Hello, we can't take your call right now. "
                "Please leave a message after the tone and we'll get back to you soon."),
            goodbye_text=self._t("תודה רבה, שלום ולהתראות.", "Thank you, goodbye."),
            max_message_sec=120,
            silence_cutoff_sec=5,
            play_goodbye=True
        )
        self._rules.append(rule)
        self._save_rules()

    # ── Public interface ─────────────────────────────────

    def get_rules(self) -> list:
        return list(self._rules)

    def add_rule(self, rule: VoicemailRule):
        self._rules.append(rule)
        self._save_rules()

    def update_rule(self, rule: VoicemailRule):
        for i, r in enumerate(self._rules):
            if r.rule_id == rule.rule_id:
                self._rules[i] = rule
                break
        self._save_rules()

    def delete_rule(self, rule_id: str):
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        self._save_rules()

    def find_matching_rule(self, number: str) -> Optional[VoicemailRule]:
        """מצא כלל תואם לשיחה נכנסת"""
        now = datetime.datetime.now()
        weekday = now.weekday()  # 0=שני..6=ראשון
        hour = now.hour

        for rule in self._rules:
            if not rule.enabled:
                continue
            # Check number
            num_match = (rule.answer_always or
                         any(number.endswith(n.strip()) or n.strip() in number
                             for n in rule.answer_numbers))
            if not num_match:
                continue
            # Check day
            if rule.answer_days and weekday not in rule.answer_days:
                continue
            # Check hour
            if not (rule.answer_hour_from <= hour <= rule.answer_hour_to):
                continue
            return rule
        return None

    def on_incoming_call(self, number: str, name: str = "") -> bool:
        """
        קרא כשמגיעה שיחה — מחזיר True אם תא קולי יטפל בה.
        """
        rule = self.find_matching_rule(number)
        if not rule:
            return False

        self._current_number = number
        self._current_name = name
        self._current_rule = rule
        self._ring_count = 0
        self._active = True
        self._state = "waiting"
        self._ring_timer.start(5000)  # ~5s per ring
        self.vm_state_changed.emit(self._t(
            f"ממתין לצלצול {rule.rings_before_answer}", f"Waiting for ring {rule.rings_before_answer}"))
        return True

    def _on_ring_tick(self):
        self._ring_count += 1
        rule = self._current_rule
        if self._ring_count >= rule.rings_before_answer:
            self._ring_timer.stop()
            self._answer_call()

    def _answer_call(self):
        if not self._active or not self.bt_mgr:
            return
        self.vm_state_changed.emit(self._t("עונה לשיחה…", "Answering call…"))
        self.vm_answering.emit(self._current_number)
        self.bt_mgr.answer_call()
        self.bt_mgr.set_mic_volume(0)   # השתק מיקרופון
        # השמע הודעת פתיח אחרי שניה
        QTimer.singleShot(1000, self._play_greeting)

    def _play_greeting(self):
        rule = self._current_rule
        self._state = "greeting"
        self.vm_state_changed.emit(self._t("משמיע הודעת פתיח…", "Playing greeting…"))
        self.vm_greeting_done.emit()
        # Estimate greeting duration (2s per 5 words) then start recording
        words = len(rule.greeting_text.split())
        est_ms = max(3000, words * 400)
        QTimer.singleShot(est_ms, self._start_vm_recording)

    def _start_vm_recording(self):
        self._state = "recording"
        self.vm_state_changed.emit(self._t("מקליט הודעה…", "Recording message…"))
        self.vm_recording.emit()

        if self.rec_mgr:
            self.rec_mgr.start_recording(
                number=self._current_number,
                name=self._current_name,
                direction="incoming",
                voicemail=True
            )

        rule = self._current_rule
        # Silence detection + max duration
        self._silence_timer.start(rule.silence_cutoff_sec * 1000)
        self._max_timer.start(rule.max_message_sec * 1000)

    def on_dtmf_received(self, tone: str):
        """# — סיים הקלטה"""
        if self._state == "recording" and tone == "#":
            self._finish_recording()

    def _on_silence_timeout(self):
        if self._state == "recording":
            self._finish_recording(reason="silence")

    def _on_max_duration(self):
        if self._state == "recording":
            self._finish_recording(reason="max_duration")

    def _finish_recording(self, reason: str = "user"):
        self._silence_timer.stop()
        self._max_timer.stop()
        self._state = "goodbye"
        self.vm_state_changed.emit(self._t("שומר הודעה…", "Saving message…"))

        entry = None
        if self.rec_mgr:
            entry = self.rec_mgr.stop_recording()
        if entry:
            self.vm_message_saved.emit(entry.filename)

        rule = self._current_rule
        if rule and rule.play_goodbye:
            words = len(rule.goodbye_text.split())
            est_ms = max(2000, words * 400)
            QTimer.singleShot(est_ms, self._end_call)
        else:
            self._end_call()

    def _end_call(self):
        if self.bt_mgr:
            self.bt_mgr.hangup()
        self._active = False
        self._state = "idle"
        self.vm_call_ended.emit()
        self.vm_state_changed.emit(self._t("שיחת תא קולי הסתיימה", "Voicemail call ended"))

    def cancel(self):
        """בטל תא קולי (המשתמש ענה ידנית)"""
        self._ring_timer.stop()
        self._silence_timer.stop()
        self._max_timer.stop()
        self._active = False
        self._state = "idle"

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def state(self) -> str:
        return self._state

    def get_greetings_dir(self) -> str:
        return str(self.greetings_dir)

    def list_greeting_files(self) -> list[str]:
        return [f.name for f in self.greetings_dir.glob("*.wav")]
