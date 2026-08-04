#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
לשונית בייביסיטר — ניטור קולי מלא
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QCheckBox, QGroupBox, QListWidget, QListWidgetItem,
    QComboBox, QLineEdit, QFrame, QScrollArea, QFileDialog,
    QTabWidget, QSpinBox, QDoubleSpinBox, QSizePolicy,
    QMessageBox, QDialog, QFormLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtGui import QFont, QColor

from app.core.babysitter_engine import (
    BabysitterEngine, BabysitterExtension, BabysitterSettings
)
from app.core.language_manager import Translatable


class ExtensionDialog(QDialog, Translatable):
    """הוסף/ערוך שלוחה"""
    def __init__(self, mics: list, language_manager, ext: BabysitterExtension = None, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.setWindowTitle(self.t("שלוחה", "Extension") if ext
                             else self.t("שלוחה חדשה", "New Extension"))
        self.setLayoutDirection(language_manager.direction)
        self.setMinimumWidth(320)
        ly = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(ext.name if ext else "")
        self.tr_set(self.name_edit, "לדוגמה: חדר תינוק", "e.g. Baby's room", setter="setPlaceholderText")
        form.addRow(self.t("שם:", "Name:"), self.name_edit)

        self.mic_combo = QComboBox()
        self.mic_combo.addItem(self.t("ברירת מחדל", "Default"), None)
        for idx, name in mics:
            self.mic_combo.addItem(name, idx)
        if ext and ext.mic_index is not None:
            for i in range(self.mic_combo.count()):
                if self.mic_combo.itemData(i) == ext.mic_index:
                    self.mic_combo.setCurrentIndex(i)
                    break
        form.addRow(self.t("מיקרופון:", "Microphone:"), self.mic_combo)

        self.chk_enabled = QCheckBox()
        self.tr_set(self.chk_enabled, "שלוחה פעילה", "Extension active")
        self.chk_enabled.setChecked(ext.enabled if ext else True)
        form.addRow("", self.chk_enabled)

        ly.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        ly.addWidget(btns)

    def get_data(self):
        return (self.name_edit.text().strip(),
                self.mic_combo.currentData(),
                self.chk_enabled.isChecked())


class BabysitterPage(QWidget, Translatable):
    def __init__(self, bt_manager, babysitter_engine: BabysitterEngine,
                 language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.bt     = bt_manager
        self.engine = babysitter_engine
        self.setObjectName("settingsPage")
        self.setLayoutDirection(language_manager.direction)

        self._level_timer = QTimer(self)
        self._level_timer.timeout.connect(self._update_level_display)
        self._peak_rms = 0.0

        self._build()
        self._connect_signals()
        self._refresh_extensions()
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self.retranslate()
        self._refresh_extensions()

    # ── Build ─────────────────────────────────────────────

    def _lbl(self, he, en):
        l = QLabel(); self.tr_set(l, he, en); return l

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True); scroll.setObjectName("settingsScroll")
        inner = QWidget(); inner.setObjectName("settingsContent")
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        ly = QVBoxLayout(inner)
        ly.setContentsMargins(20, 16, 20, 20); ly.setSpacing(14)

        # ── Title + master switch ──
        title_row = QHBoxLayout()
        title = QLabel()
        title.setObjectName("pageTitle"); title_row.addWidget(title)
        self.tr_set(title, "בייביסיטר", "Baby Monitor")
        title_row.addStretch()
        self.btn_toggle = QPushButton()
        self.tr_set(self.btn_toggle, "הפעל ניטור", "Start Monitoring")
        self.btn_toggle.setObjectName("primaryButton")
        self.btn_toggle.setMinimumWidth(130)
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.clicked.connect(self._toggle_monitoring)
        title_row.addWidget(self.btn_toggle)
        ly.addLayout(title_row)

        # Status + level meter
        status_frame = QFrame(); status_frame.setObjectName("playbackBar")
        sly = QHBoxLayout(status_frame); sly.setContentsMargins(12, 8, 12, 8)
        self.status_lbl = QLabel()
        self.status_lbl.setObjectName("callStatus"); self.status_lbl.setFont(QFont("Segoe UI", 10))
        self.tr_set(self.status_lbl, "ניטור כבוי", "Monitoring off")
        sly.addWidget(self.status_lbl)
        sly.addStretch()
        self.alert_lbl = QLabel("")
        self.alert_lbl.setObjectName("recIndicator"); self.alert_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        sly.addWidget(self.alert_lbl)
        ly.addWidget(status_frame)

        # ── Extensions ──
        eg = self._group("שלוחות (חדרים מנוטרים)", "Extensions (Monitored Rooms)")
        ely = QVBoxLayout()
        ely.addWidget(self._lbl("הגדר שלוחה לכל חדר שברצונך לנטר:",
                                 "Set up an extension for each room you want to monitor:"))
        self.ext_list = QListWidget()
        self.ext_list.setObjectName("callLogList"); self.ext_list.setMaximumHeight(130)
        ely.addWidget(self.ext_list)
        ext_btns = QHBoxLayout()
        btn_add_ext = QPushButton(); self.tr_set(btn_add_ext, "הוסף שלוחה", "Add Extension")
        btn_add_ext.setObjectName("secondaryButton")
        btn_add_ext.setCursor(Qt.CursorShape.PointingHandCursor); btn_add_ext.clicked.connect(self._add_extension)
        btn_edit_ext = QPushButton(); self.tr_set(btn_edit_ext, "ערוך", "Edit")
        btn_edit_ext.setObjectName("secondaryButton")
        btn_edit_ext.setCursor(Qt.CursorShape.PointingHandCursor); btn_edit_ext.clicked.connect(self._edit_extension)
        btn_del_ext = QPushButton(); self.tr_set(btn_del_ext, "מחק", "Delete")
        btn_del_ext.setObjectName("secondaryButton")
        btn_del_ext.setCursor(Qt.CursorShape.PointingHandCursor); btn_del_ext.clicked.connect(self._del_extension)
        for b in [btn_add_ext, btn_edit_ext, btn_del_ext]: ext_btns.addWidget(b)
        ext_btns.addStretch(); ely.addLayout(ext_btns)
        eg.setLayout(ely); ly.addWidget(eg)

        # ── Alert numbers ──
        ng = self._group("מספרי התראה", "Alert Numbers")
        nly = QVBoxLayout()
        nly.addWidget(self._lbl("מספרי טלפון לחייג כשמזוהה קול (בסדר עדיפות):",
                                 "Phone numbers to call when sound is detected (in priority order):"))
        self.numbers_list = QListWidget()
        self.numbers_list.setObjectName("callLogList"); self.numbers_list.setMaximumHeight(110)
        nly.addWidget(self.numbers_list)
        nr = QHBoxLayout()
        self.num_input = QLineEdit(); self.num_input.setPlaceholderText("050-1234567")
        self.num_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight); nr.addWidget(self.num_input)
        btn_add_num = QPushButton(); self.tr_set(btn_add_num, "הוסף", "Add")
        btn_add_num.setObjectName("smallButton")
        btn_add_num.setCursor(Qt.CursorShape.PointingHandCursor); btn_add_num.clicked.connect(self._add_number)
        btn_del_num = QPushButton(); self.tr_set(btn_del_num, "מחק", "Delete")
        btn_del_num.setObjectName("smallButton")
        btn_del_num.setCursor(Qt.CursorShape.PointingHandCursor); btn_del_num.clicked.connect(self._del_number)
        nr.addWidget(btn_add_num); nr.addWidget(btn_del_num); nly.addLayout(nr)

        ring_row = QHBoxLayout()
        ring_row.addWidget(self._lbl("המתן לפני עבור למספר הבא (שניות):",
                                      "Wait before moving to next number (seconds):"))
        self.ring_spin = QSpinBox(); self.ring_spin.setRange(5, 120); self.ring_spin.setValue(20)
        self.ring_spin.valueChanged.connect(
            lambda v: setattr(self.engine.settings, 'ring_timeout_sec', v))
        ring_row.addWidget(self.ring_spin); ring_row.addStretch()
        nly.addLayout(ring_row)
        ng.setLayout(nly); ly.addWidget(ng)

        # ── Sensitivity ──
        sg = self._group("רגישות זיהוי", "Detection Sensitivity")
        senly = QVBoxLayout()
        senly.addWidget(self._lbl("מצב ניטור:", "Monitoring mode:"))
        self.mode_combo = QComboBox(); self.mode_combo.setObjectName("filterCombo")
        self.mode_combo.addItem(self.t("זיהוי בכי בלבד", "Crying detection only"), "cry")
        self.mode_combo.addItem(self.t("זיהוי קול/דיבור בלבד", "Voice/speech detection only"), "voice")
        self.mode_combo.addItem(self.t("זיהוי בכי ודיבור (כל קול)", "Crying and speech (any sound)"), "both")
        self.mode_combo.currentIndexChanged.connect(
            lambda: setattr(self.engine.settings, 'monitor_mode',
                           self.mode_combo.currentData()))
        senly.addWidget(self.mode_combo)

        senly.addWidget(self._lbl("רגישות (גבוה = יזהה גם קולות חלשים):",
                                   "Sensitivity (higher = detects fainter sounds too):"))
        sens_row = QHBoxLayout()
        self.sens_slider = QSlider(Qt.Orientation.Horizontal)
        self.sens_slider.setRange(0, 100); self.sens_slider.setValue(35)
        self.sens_slider.setObjectName("settingSlider")
        self.sens_slider.valueChanged.connect(self._on_sensitivity_changed)
        sens_row.addWidget(self.sens_slider)
        self.sens_lbl = QLabel("35%"); self.sens_lbl.setFixedWidth(40)
        sens_row.addWidget(self.sens_lbl); senly.addLayout(sens_row)

        sens_presets = QHBoxLayout()
        for he, en, val in [("נמוכה", "Low", 15), ("בינונית", "Medium", 35),
                             ("גבוהה", "High", 60), ("מקסימום", "Maximum", 85)]:
            b = QPushButton(); self.tr_set(b, he, en); b.setObjectName("smallButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, v=val: self.sens_slider.setValue(v))
            sens_presets.addWidget(b)
        sens_presets.addStretch(); senly.addLayout(sens_presets)

        dur_row = QHBoxLayout()
        dur_row.addWidget(self._lbl("משך קול מינימלי לפני התראה (שניות):",
                                     "Minimum sound duration before alert (seconds):"))
        self.dur_spin = QDoubleSpinBox(); self.dur_spin.setRange(0.5, 10.0)
        self.dur_spin.setSingleStep(0.5); self.dur_spin.setValue(1.5)
        self.dur_spin.valueChanged.connect(
            lambda v: setattr(self.engine.settings, 'min_sound_duration_sec', v))
        dur_row.addWidget(self.dur_spin); dur_row.addStretch()
        senly.addLayout(dur_row)

        gap_row = QHBoxLayout()
        gap_row.addWidget(self._lbl("שתיקה לאחר קול לפני עצירת זיהוי (שניות):",
                                     "Silence after sound before stopping detection (seconds):"))
        self.gap_spin = QDoubleSpinBox(); self.gap_spin.setRange(1.0, 30.0)
        self.gap_spin.setSingleStep(1.0); self.gap_spin.setValue(3.0)
        self.gap_spin.valueChanged.connect(
            lambda v: setattr(self.engine.settings, 'silence_gap_sec', v))
        gap_row.addWidget(self.gap_spin); gap_row.addStretch()
        senly.addLayout(gap_row)
        sg.setLayout(senly); ly.addWidget(sg)

        # ── Alert file ──
        ag = self._group("קובץ התראה", "Alert Sound File")
        aly = QVBoxLayout()
        aly.addWidget(self._lbl("קובץ שמע להשמעה כשהשיחה נענית:",
                                 "Audio file to play once the call is answered:"))
        afr = QHBoxLayout()
        self.alert_file_lbl = QLabel()
        self.tr_set(self.alert_file_lbl, "לא נבחר", "Not selected")
        self.alert_file_lbl.setObjectName("infoLabel"); afr.addWidget(self.alert_file_lbl, 1)
        btn_pick = QPushButton(); self.tr_set(btn_pick, "בחר קובץ WAV", "Choose WAV File")
        btn_pick.setObjectName("secondaryButton")
        btn_pick.setCursor(Qt.CursorShape.PointingHandCursor); btn_pick.clicked.connect(self._pick_alert_file)
        afr.addWidget(btn_pick); aly.addLayout(afr)
        ag.setLayout(aly); ly.addWidget(ag)

        # ── Auto answer ──
        aag = self._group("מענה אוטומטי לשיחה נכנסת", "Automatic Answer for Incoming Calls")
        aaly = QVBoxLayout()
        self.chk_auto_answer = QCheckBox()
        self.tr_set(self.chk_auto_answer, "ענה אוטומטית לחיוג ממספרים מורשים",
                    "Automatically answer calls from authorized numbers")
        self.chk_auto_answer.setChecked(True)
        self.chk_auto_answer.toggled.connect(
            lambda v: setattr(self.engine.settings, 'auto_answer', v))
        aaly.addWidget(self.chk_auto_answer)
        aaly.addWidget(self._lbl("מספרים מורשים לחיוג (ריק = כולם):",
                                  "Authorized numbers to call from (empty = everyone):"))
        self.callers_list = QListWidget()
        self.callers_list.setObjectName("callLogList"); self.callers_list.setMaximumHeight(80)
        aaly.addWidget(self.callers_list)
        calr = QHBoxLayout()
        self.caller_input = QLineEdit(); self.caller_input.setPlaceholderText("050-…")
        self.caller_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight); calr.addWidget(self.caller_input)
        btn_add_c = QPushButton(); self.tr_set(btn_add_c, "הוסף", "Add")
        btn_add_c.setObjectName("smallButton")
        btn_add_c.setCursor(Qt.CursorShape.PointingHandCursor); btn_add_c.clicked.connect(self._add_caller)
        btn_del_c = QPushButton(); self.tr_set(btn_del_c, "מחק", "Delete")
        btn_del_c.setObjectName("smallButton")
        btn_del_c.setCursor(Qt.CursorShape.PointingHandCursor); btn_del_c.clicked.connect(self._del_caller)
        calr.addWidget(btn_add_c); calr.addWidget(btn_del_c); aaly.addLayout(calr)
        aaly.addWidget(self._lbl("כשמתחברים — שומעים בשידור חי מהשלוחה הפעילה",
                                  "Once connected — you'll hear a live feed from the active extension"))
        aag.setLayout(aaly); ly.addWidget(aag)

        # ── Save ──
        btn_save = QPushButton()
        self.tr_set(btn_save, "שמור הגדרות", "Save Settings")
        btn_save.setObjectName("primaryButton")
        btn_save.setMinimumHeight(42)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._save_settings)
        ly.addWidget(btn_save)
        ly.addStretch()

    def _group(self, he, en) -> QGroupBox:
        g = QGroupBox(); g.setObjectName("settingsGroup")
        self.tr_set(g, he, en, setter="setTitle")
        g.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold)); return g

    # ── Connect signals ───────────────────────────────────

    def _connect_signals(self):
        self.engine.status_changed.connect(self.status_lbl.setText)
        self.engine.alert_triggered.connect(self._on_alert)
        self.engine.monitoring_started.connect(
            lambda: self.tr_set(self.btn_toggle, "עצור ניטור", "Stop Monitoring"))
        self.engine.monitoring_stopped.connect(
            lambda: self.tr_set(self.btn_toggle, "הפעל ניטור", "Start Monitoring"))
        self.engine.error_occurred.connect(
            lambda e: self.status_lbl.setText(self.t(f"שגיאה: {e}", f"Error: {e}")))

    # ── Extensions ────────────────────────────────────────

    def _refresh_extensions(self):
        self.ext_list.clear()
        for ext in self.engine.settings.extensions:
            status = self.t("פעיל", "Active") if ext.enabled else self.t("כבוי", "Off")
            mic = f" — {self.t('מיק', 'Mic')} #{ext.mic_index}" if ext.mic_index is not None else ""
            item = QListWidgetItem(f"{ext.name}  [{status}]{mic}")
            item.setData(Qt.ItemDataRole.UserRole, ext.ext_id)
            self.ext_list.addItem(item)

    def _add_extension(self):
        mics = self.engine.get_available_microphones()
        dlg = ExtensionDialog(mics, self._lang_mgr, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, mic_idx, enabled = dlg.get_data()
            if name:
                ext = self.engine.add_extension(name, mic_idx)
                ext.enabled = enabled
                self._refresh_extensions()

    def _edit_extension(self):
        item = self.ext_list.currentItem()
        if not item: return
        ext_id = item.data(Qt.ItemDataRole.UserRole)
        ext = next((e for e in self.engine.settings.extensions
                    if e.ext_id == ext_id), None)
        if not ext: return
        mics = self.engine.get_available_microphones()
        dlg = ExtensionDialog(mics, self._lang_mgr, ext=ext, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, mic_idx, enabled = dlg.get_data()
            if name:
                ext.name = name; ext.mic_index = mic_idx; ext.enabled = enabled
                self._refresh_extensions()

    def _del_extension(self):
        item = self.ext_list.currentItem()
        if item:
            self.engine.remove_extension(item.data(Qt.ItemDataRole.UserRole))
            self._refresh_extensions()

    # ── Numbers ───────────────────────────────────────────

    def _add_number(self):
        n = self.num_input.text().strip()
        if n and n not in self.engine.settings.call_numbers:
            self.engine.settings.call_numbers.append(n)
            self.numbers_list.addItem(n)
            self.num_input.clear()

    def _del_number(self):
        item = self.numbers_list.currentItem()
        if item:
            self.engine.settings.call_numbers.remove(item.text())
            self.numbers_list.takeItem(self.numbers_list.row(item))

    def _add_caller(self):
        n = self.caller_input.text().strip()
        if n and n not in self.engine.settings.allowed_callers:
            self.engine.settings.allowed_callers.append(n)
            self.callers_list.addItem(n)
            self.caller_input.clear()

    def _del_caller(self):
        item = self.callers_list.currentItem()
        if item:
            self.engine.settings.allowed_callers.remove(item.text())
            self.callers_list.takeItem(self.callers_list.row(item))

    # ── Sensitivity ───────────────────────────────────────

    def _on_sensitivity_changed(self, val: int):
        self.sens_lbl.setText(f"{val}%")
        self.engine.settings.sensitivity = val / 100.0

    # ── Alert file ────────────────────────────────────────

    def _pick_alert_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.t("בחר קובץ שמע", "Select Audio File"), "", "WAV Files (*.wav);;All Files (*)")
        if path:
            self.engine.settings.alert_file = path
            self.alert_file_lbl.setText(os.path.basename(path))

    # ── Monitoring toggle ─────────────────────────────────

    def _toggle_monitoring(self):
        if self.engine.settings.enabled:
            self.engine.stop_monitoring()
            self._level_timer.stop()
        else:
            self.engine.start_monitoring()
            self._level_timer.start(500)

    # ── Alert display ─────────────────────────────────────

    def _on_alert(self, ext_id: str, ext_name: str):
        self.alert_lbl.setText(self.t(f"קול זוהה: {ext_name}", f"Sound detected: {ext_name}"))
        QTimer.singleShot(8000, lambda: self.alert_lbl.setText(""))

    def _update_level_display(self):
        pass   # Could show live VU meter in future

    # ── Save ─────────────────────────────────────────────

    def _save_settings(self):
        self.engine.settings.ring_timeout_sec = self.ring_spin.value()
        self.engine.settings.min_sound_duration_sec = self.dur_spin.value()
        self.engine.settings.silence_gap_sec = self.gap_spin.value()
        self.engine.settings.sensitivity = self.sens_slider.value() / 100.0
        self.engine.settings.monitor_mode = self.mode_combo.currentData()
        self.engine.save_settings()
        QMessageBox.information(self, self.t("שמירה", "Saved"),
                                 self.t("ההגדרות נשמרו בהצלחה", "Settings saved successfully"))
