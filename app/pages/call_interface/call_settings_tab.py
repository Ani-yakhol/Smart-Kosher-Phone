#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""לשונית הגדרות שיחה — שמע + הקלטה + זיהוי קול DTMF"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QCheckBox, QGroupBox, QLineEdit, QListWidget,
    QSpinBox, QComboBox, QScrollArea, QFrame, QProgressBar,
    QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
import os

from app.core.language_manager import Translatable


class CallSettingsTab(QWidget, Translatable):
    def __init__(self, bt_manager, language_manager, rec_manager=None,
                 voice_recognizer=None, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.bt   = bt_manager
        self.rec  = rec_manager
        self.vr   = voice_recognizer   # VoiceRecognizer instance
        self.setObjectName("settingsPage")
        self.setLayoutDirection(language_manager.direction)
        self._build()
        if self.vr:
            self._connect_vr_signals()
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self.retranslate()

    def _lbl(self, he, en):
        l = QLabel()
        self.tr_set(l, he, en)
        return l

    def _build(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setObjectName("settingsScroll")
        content = QWidget(); content.setObjectName("settingsContent")
        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        outer.addWidget(scroll)
        ly = QVBoxLayout(content)
        ly.setContentsMargins(20,16,20,20); ly.setSpacing(16)

        # ── Audio ──
        ag = self._group("🔊 שמע", "🔊 Audio")
        aly = QVBoxLayout()
        aly.addWidget(self._lbl("עוצמת קול (0-15):", "Volume (0-15):"))
        vr = QHBoxLayout()
        self.vol_slider = QSlider(Qt.Orientation.Horizontal); self.vol_slider.setRange(0,15)
        self.vol_slider.setValue(10); self.vol_slider.setObjectName("settingSlider")
        self.vol_slider.valueChanged.connect(self.bt.set_volume)
        vr.addWidget(self.vol_slider)
        self.vol_lbl = QLabel("10"); self.vol_lbl.setFixedWidth(28)
        self.vol_slider.valueChanged.connect(lambda v: self.vol_lbl.setText(str(v)))
        vr.addWidget(self.vol_lbl); aly.addLayout(vr)

        aly.addWidget(self._lbl("עוצמת מיקרופון (0-15):", "Microphone level (0-15):"))
        mr = QHBoxLayout()
        self.mic_slider = QSlider(Qt.Orientation.Horizontal); self.mic_slider.setRange(0,15)
        self.mic_slider.setValue(10); self.mic_slider.setObjectName("settingSlider")
        self.mic_slider.valueChanged.connect(self.bt.set_mic_volume)
        mr.addWidget(self.mic_slider)
        self.mic_lbl = QLabel("10"); self.mic_lbl.setFixedWidth(28)
        self.mic_slider.valueChanged.connect(lambda v: self.mic_lbl.setText(str(v)))
        mr.addWidget(self.mic_lbl); aly.addLayout(mr)

        # Microphone selector
        aly.addWidget(self._lbl("מיקרופון לדיבור:", "Input microphone:"))
        self.mic_combo = QComboBox(); self.mic_combo.setObjectName("filterCombo")
        self.mic_combo.addItem(self.t("ברירת מחדל", "Default"), None)
        if self.vr:
            for idx, name in self.vr.get_available_microphones():
                self.mic_combo.addItem(name, idx)
        self.mic_combo.currentIndexChanged.connect(self._on_mic_selected)
        aly.addWidget(self.mic_combo)

        refresh_mic = QPushButton()
        self.tr_set(refresh_mic, "🔄 רענן רשימת מיקרופונים", "🔄 Refresh Microphone List")
        refresh_mic.setObjectName("smallButton"); refresh_mic.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_mic.clicked.connect(self._refresh_mics)
        aly.addWidget(refresh_mic)
        ag.setLayout(aly); ly.addWidget(ag)

        # ── Voice DTMF Recognition ──
        vg = self._group("🎙️ זיהוי קול לשליחת DTMF", "🎙️ Voice Recognition for DTMF")
        vly = QVBoxLayout()

        # Engine status
        engine_name = getattr(self.vr, 'engine', None) or self.t("לא זמין", "Unavailable")
        self.engine_lbl = QLabel()
        self.tr_set(self.engine_lbl, f"מנוע זיהוי: {engine_name}", f"Recognition engine: {engine_name}")
        self.engine_lbl.setObjectName("infoLabel"); vly.addWidget(self.engine_lbl)

        # Enable toggle
        self.chk_voice_dtmf = QCheckBox()
        self.tr_set(self.chk_voice_dtmf, "הפעל זיהוי קול ל-DTMF", "Enable voice recognition for DTMF")
        self.chk_voice_dtmf.toggled.connect(self._toggle_voice_dtmf)
        vly.addWidget(self.chk_voice_dtmf)

        # Status
        self.vr_status_lbl = QLabel()
        self.tr_set(self.vr_status_lbl, "לא פעיל", "Inactive")
        self.vr_status_lbl.setObjectName("infoLabel"); vly.addWidget(self.vr_status_lbl)

        # Last recognized
        last_row = QHBoxLayout()
        last_row.addWidget(self._lbl("ספרה אחרונה שזוהתה:", "Last digit recognized:"))
        self.last_digit_lbl = QLabel("—")
        self.last_digit_lbl.setObjectName("callTimer")
        self.last_digit_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        last_row.addWidget(self.last_digit_lbl); last_row.addStretch()
        vly.addLayout(last_row)

        # Instructions
        inst = QLabel()
        self.tr_set(inst,
            "כיצד לשתמש:\n"
            "1. בזמן שיחה פעילה, הפעל זיהוי קול\n"
            "2. אמור את שם הספרה בעברית (אחד, שתיים…)\n"
            "3. המחשב ישלח אוטומטית את טון ה-DTMF לשיחה",
            "How to use:\n"
            "1. During an active call, enable voice recognition\n"
            "2. Say the digit's name out loud (one, two…)\n"
            "3. The computer will automatically send the DTMF tone to the call")
        inst.setObjectName("infoLabel"); inst.setWordWrap(True)
        vly.addWidget(inst)

        # Vosk model section
        vly.addWidget(self._lbl("מודל Vosk (אופליין):", "Vosk model (offline):"))
        self.model_combo = QComboBox(); self.model_combo.setObjectName("filterCombo")
        self.model_combo.addItem(self.t("ללא מודל — השתמש בזיהוי אונליין",
                                          "No model — use online recognition"))
        if self.vr:
            for m in self.vr.list_vosk_models():
                self.model_combo.addItem(m)
        vly.addWidget(self.model_combo)

        model_row = QHBoxLayout()
        btn_load = QPushButton(); self.tr_set(btn_load, "טען מודל", "Load Model")
        btn_load.setObjectName("secondaryButton")
        btn_load.setCursor(Qt.CursorShape.PointingHandCursor); btn_load.clicked.connect(self._load_vosk_model)
        model_row.addWidget(btn_load)
        btn_dl = QPushButton(); self.tr_set(btn_dl, "🌐 הורד מודל", "🌐 Download Model")
        btn_dl.setObjectName("secondaryButton")
        btn_dl.setCursor(Qt.CursorShape.PointingHandCursor); btn_dl.clicked.connect(self._open_vosk_site)
        model_row.addWidget(btn_dl); model_row.addStretch()
        vly.addLayout(model_row)
        vg.setLayout(vly); ly.addWidget(vg)

        # ── Voice Training ──
        tg = self._group("🏋️ אימון זיהוי קול", "🏋️ Voice Recognition Training")
        tly = QVBoxLayout()
        tly.addWidget(self._lbl(
            "הקלט דגימות אימון לשיפור הזיהוי:\nלחץ על ספרה, אמור אותה, ההקלטה תישמר.",
            "Record training samples to improve recognition:\n"
            "Click a digit, say it out loud, the recording is saved."))

        digits_frame = QFrame()
        dly = QHBoxLayout(digits_frame); dly.setSpacing(8)
        for d in "0 1 2 3 4 5 6 7 8 9 * #".split():
            btn = QPushButton(d); btn.setObjectName("dtmfButton")
            btn.setFixedSize(44, 44); btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, digit=d: self._record_training(digit))
            dly.addWidget(btn)
        dly.addStretch()
        tly.addWidget(digits_frame)

        self.train_status = QLabel(""); self.train_status.setObjectName("infoLabel")
        tly.addWidget(self.train_status)
        tg.setLayout(tly); ly.addWidget(tg)

        # ── Auto Recording ──
        rg = self._group("⏺ הקלטה אוטומטית", "⏺ Automatic Recording")
        rly = QVBoxLayout()
        self.chk_rec_all = QCheckBox()
        self.tr_set(self.chk_rec_all, "הקלט את כל השיחות", "Record all calls")
        self.chk_rec_all.toggled.connect(self._on_rec_all)
        rly.addWidget(self.chk_rec_all)
        rly.addWidget(self._lbl("מספרים ספציפיים להקלטה:", "Specific numbers to record:"))
        nr = QHBoxLayout()
        self.rec_num_input = QLineEdit()
        self.rec_num_input.setPlaceholderText("050-…")
        self.rec_num_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight); nr.addWidget(self.rec_num_input)
        btn_add = QPushButton(); self.tr_set(btn_add, "הוסף", "Add")
        btn_add.setObjectName("smallButton")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor); btn_add.clicked.connect(self._add_rec_num)
        nr.addWidget(btn_add); rly.addLayout(nr)
        self.rec_nums_list = QListWidget(); self.rec_nums_list.setObjectName("smallList")
        self.rec_nums_list.setMaximumHeight(90); rly.addWidget(self.rec_nums_list)
        del_btn = QPushButton(); self.tr_set(del_btn, "מחק נבחר", "Delete Selected")
        del_btn.setObjectName("smallButton")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor); del_btn.clicked.connect(self._del_rec_num)
        rly.addWidget(del_btn)
        rg.setLayout(rly); ly.addWidget(rg)

        # ── Demo ──
        dg = self._group("🧪 הדגמה", "🧪 Demo")
        dly2 = QVBoxLayout()
        dr = QHBoxLayout()
        b1 = QPushButton(); self.tr_set(b1, "📲 שיחה נכנסת", "📲 Incoming Call")
        b1.setObjectName("secondaryButton")
        b1.setCursor(Qt.CursorShape.PointingHandCursor)
        b1.clicked.connect(lambda: self.bt.simulate_incoming_call(
            "0501234567", self.t("אבא", "Dad")))
        b2 = QPushButton(); self.tr_set(b2, "📞 חיוג יוצא", "📞 Outgoing Call")
        b2.setObjectName("secondaryButton")
        b2.setCursor(Qt.CursorShape.PointingHandCursor)
        b2.clicked.connect(lambda: self.bt.dial("0521234567"))
        dr.addWidget(b1); dr.addWidget(b2); dly2.addLayout(dr)
        dg.setLayout(dly2); ly.addWidget(dg)
        ly.addStretch()

    def _group(self, he, en):
        g = QGroupBox(); g.setObjectName("settingsGroup")
        self.tr_set(g, he, en, setter="setTitle")
        g.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold)); return g

    def _connect_vr_signals(self):
        if not self.vr: return
        self.vr.digit_recognized.connect(self._on_digit_recognized)
        self.vr.status_changed.connect(self.vr_status_lbl.setText)
        self.vr.error_occurred.connect(
            lambda e: self.vr_status_lbl.setText(f"⚠️ {e}"))

    def _on_mic_selected(self, idx: int):
        mic_idx = self.mic_combo.currentData()
        if self.vr: self.vr.set_microphone(mic_idx)

    def _refresh_mics(self):
        self.mic_combo.clear()
        self.mic_combo.addItem(self.t("ברירת מחדל", "Default"), None)
        if self.vr:
            for idx, name in self.vr.get_available_microphones():
                self.mic_combo.addItem(name, idx)

    def _toggle_voice_dtmf(self, enabled: bool):
        if not self.vr: return
        if enabled:
            self.vr.start_listening()
            self.vr_status_lbl.setText(self.t("🎙️ מאזין…", "🎙️ Listening…"))
        else:
            self.vr.stop_listening()
            self.vr_status_lbl.setText(self.t("כבוי", "Off"))

    def _on_digit_recognized(self, digit: str):
        self.last_digit_lbl.setText(digit)
        # Flash effect
        QTimer.singleShot(1500, lambda: self.last_digit_lbl.setText("—"))

    def _load_vosk_model(self):
        path = QFileDialog.getExistingDirectory(
            self, self.t("בחר תיקיית מודל Vosk", "Select Vosk Model Folder"))
        if path and self.vr:
            if self.vr.load_vosk_model(path):
                self.model_combo.addItem(os.path.basename(path))

    def _open_vosk_site(self):
        import subprocess
        subprocess.Popen(["start", "https://alphacephei.com/vosk/models"],
                         shell=True)

    def _record_training(self, digit: str):
        if not self.vr: return
        import os
        base = os.path.join(os.path.expanduser("~"), "BluePhone", "training")
        os.makedirs(base, exist_ok=True)
        import time
        path = os.path.join(base, f"{digit}_{int(time.time())}.wav")
        self.train_status.setText(self.t(f"מקליט '{digit}'… אמור את הספרה",
                                           f"Recording '{digit}'… say the digit"))
        def done(ok, result):
            if ok:
                self.train_status.setText(self.t(f"✅ נשמר: {os.path.basename(result)}",
                                                   f"✅ Saved: {os.path.basename(result)}"))
            else:
                self.train_status.setText(self.t(f"⚠️ שגיאה: {result}", f"⚠️ Error: {result}"))
        self.vr.record_training_sample(digit, path, duration=2.0, callback=done)

    def _on_rec_all(self, checked):
        if self.rec: self.rec.auto_record_all = checked

    def _add_rec_num(self):
        n = self.rec_num_input.text().strip()
        if n:
            self.rec_nums_list.addItem(n)
            self.rec_num_input.clear()
            if self.rec: self.rec.auto_record_numbers.add(n)

    def _del_rec_num(self):
        item = self.rec_nums_list.currentItem()
        if item:
            n = item.text()
            self.rec_nums_list.takeItem(self.rec_nums_list.row(item))
            if self.rec: self.rec.auto_record_numbers.discard(n)
