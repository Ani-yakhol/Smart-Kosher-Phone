#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SmartHomePage — לשונית בית חכם
שליטה ברכיבי בית חכם (כגון פיוז חכם) המחוברים לקו טלפוני, ע"י שליחת
הקשות DTMF דרך אותה תשתית שכבר משמשת לחיוג/מענה/DTMF בשאר התוכנה.
"""

import os, uuid
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QSpinBox, QComboBox,
    QCheckBox, QFrame, QGroupBox, QDialog, QFormLayout,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QScrollArea, QSizePolicy, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtGui import QFont

from app.core.smart_home_engine import SmartHomeEngine, SmartHomeDevice, DeviceState
from app.core.language_manager import Translatable


# ─────────────────────────────────────────────────────────
#  Device editor dialog
# ─────────────────────────────────────────────────────────
class DeviceEditorDialog(QDialog, Translatable):
    def __init__(self, language_manager, device: SmartHomeDevice = None, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self._device = device
        self._states: list[DeviceState] = list(device.states) if device else []
        self.setWindowTitle(self.t("עריכת רכיב", "Edit Device") if device
                             else self.t("רכיב חדש", "New Device"))
        self.setLayoutDirection(language_manager.direction)
        self.setMinimumWidth(440)
        self._build()
        if device:
            self._load(device)

    def _build(self):
        ly = QVBoxLayout(self)
        ly.setSpacing(12)
        form = QFormLayout(); form.setSpacing(9)

        self.name_edit = QLineEdit()
        self.tr_set(self.name_edit, "לדוגמה: תנור בסלון", "e.g. Living Room Heater", setter="setPlaceholderText")
        form.addRow(self.t("שם הרכיב:", "Device name:"), self.name_edit)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("1")
        self.key_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        form.addRow(self.t("מקש בחירה:", "Selection key:"), self.key_edit)

        self.on_edit = QLineEdit()
        self.on_edit.setPlaceholderText("1")
        self.on_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        form.addRow(self.t("מקש הפעלה:", "Turn-on key:"), self.on_edit)

        self.off_edit = QLineEdit()
        self.off_edit.setPlaceholderText("2")
        self.off_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        form.addRow(self.t("מקש כיבוי:", "Turn-off key:"), self.off_edit)

        self.timed_spin = QSpinBox()
        self.timed_spin.setRange(1, 720)
        self.timed_spin.setValue(30)
        self.timed_spin.setSuffix(" " + self.t("דקות", "min"))
        form.addRow(self.t("משך פעולה מתוזמנת ברירת מחדל:", "Default timed duration:"), self.timed_spin)

        self.chk_enabled = QCheckBox()
        self.tr_set(self.chk_enabled, "רכיב פעיל", "Device active")
        self.chk_enabled.setChecked(True)
        form.addRow("", self.chk_enabled)

        ly.addLayout(form)

        # ── Custom states table ──
        states_lbl = QLabel()
        self.tr_set(states_lbl, "מצבים נוספים (מעבר להפעלה/כיבוי):", "Additional states (beyond on/off):")
        ly.addWidget(states_lbl)

        self.states_table = QTableWidget(0, 2)
        self.states_table.setHorizontalHeaderLabels(
            [self.t("שם המצב", "State name"), self.t("רצף מקשים", "Key sequence")])
        self.states_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.states_table.setMaximumHeight(120)
        ly.addWidget(self.states_table)

        st_row = QHBoxLayout()
        btn_add_state = QPushButton()
        self.tr_set(btn_add_state, "➕ הוסף מצב", "➕ Add State")
        btn_add_state.setObjectName("secondaryButton")
        btn_add_state.clicked.connect(self._add_state_row)
        btn_del_state = QPushButton()
        self.tr_set(btn_del_state, "🗑 מחק מצב", "🗑 Delete State")
        btn_del_state.setObjectName("secondaryButton")
        btn_del_state.clicked.connect(self._del_state_row)
        st_row.addWidget(btn_add_state); st_row.addWidget(btn_del_state); st_row.addStretch()
        ly.addLayout(st_row)

        # ── Nickname info ──
        nick_lbl = QLabel()
        self.tr_set(nick_lbl,
            "💡 ניתן להקליט הכרזה קולית לרכיב זה (שם + מקש) מתוך רשימת "
            "הרכיבים לאחר השמירה — ההכרזה תעזור לזהות איזה מקש שייך לאיזה רכיב.",
            "💡 You can record a spoken announcement for this device (name + key) "
            "from the device list after saving — it helps identify which key belongs to which device.")
        nick_lbl.setObjectName("infoLabel")
        nick_lbl.setWordWrap(True)
        ly.addWidget(nick_lbl)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        ly.addWidget(btns)

    def _add_state_row(self):
        r = self.states_table.rowCount()
        self.states_table.insertRow(r)
        self.states_table.setItem(r, 0, QTableWidgetItem(""))
        self.states_table.setItem(r, 1, QTableWidgetItem(""))

    def _del_state_row(self):
        r = self.states_table.currentRow()
        if r >= 0:
            self.states_table.removeRow(r)

    def _load(self, device: SmartHomeDevice):
        self.name_edit.setText(device.name)
        self.key_edit.setText(device.key)
        self.on_edit.setText(device.on_seq)
        self.off_edit.setText(device.off_seq)
        self.timed_spin.setValue(device.default_timed_minutes)
        self.chk_enabled.setChecked(device.enabled)
        for state in device.states:
            r = self.states_table.rowCount()
            self.states_table.insertRow(r)
            self.states_table.setItem(r, 0, QTableWidgetItem(state.name))
            self.states_table.setItem(r, 1, QTableWidgetItem(state.key_sequence))

    def get_device(self) -> SmartHomeDevice:
        device_id = self._device.device_id if self._device else str(uuid.uuid4())[:8]
        states = []
        for r in range(self.states_table.rowCount()):
            name_item = self.states_table.item(r, 0)
            key_item = self.states_table.item(r, 1)
            name = name_item.text().strip() if name_item else ""
            key = key_item.text().strip() if key_item else ""
            if name and key:
                states.append(DeviceState(name=name, key_sequence=key))
        return SmartHomeDevice(
            device_id=device_id,
            name=self.name_edit.text().strip() or self.t("רכיב חדש", "New device"),
            key=self.key_edit.text().strip(),
            on_seq=self.on_edit.text().strip(),
            off_seq=self.off_edit.text().strip(),
            states=states,
            nickname_audio=self._device.nickname_audio if self._device else "",
            default_timed_minutes=self.timed_spin.value(),
            enabled=self.chk_enabled.isChecked(),
        )


# ─────────────────────────────────────────────────────────
#  Device control card (shown in the "control panel" list)
# ─────────────────────────────────────────────────────────
class DeviceControlCard(QFrame, Translatable):
    def __init__(self, device: SmartHomeDevice, engine: SmartHomeEngine,
                 language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.device = device
        self.engine = engine
        self.setObjectName("settingsGroup")
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_countdown)
        self._timer.start(1000)

    def _build(self):
        ly = QVBoxLayout(self)
        ly.setContentsMargins(14, 12, 14, 12); ly.setSpacing(8)

        top = QHBoxLayout()
        name_lbl = QLabel(f"🔌  {self.device.name}")
        name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        top.addWidget(name_lbl)
        top.addStretch()
        key_lbl = QLabel(f"{self.t('מקש', 'Key')}: {self.device.key or '—'}")
        key_lbl.setObjectName("infoLabel")
        key_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        top.addWidget(key_lbl)
        self.play_btn = QPushButton("🔊")
        self.play_btn.setFixedWidth(34)
        self.play_btn.setToolTip(self.t("נגן הכרזה", "Play announcement"))
        self.play_btn.clicked.connect(lambda: self.engine.play_nickname(self.device.device_id))
        top.addWidget(self.play_btn)
        ly.addLayout(top)

        self.countdown_lbl = QLabel("")
        self.countdown_lbl.setObjectName("recIndicator")
        ly.addWidget(self.countdown_lbl)

        btn_row = QHBoxLayout()
        btn_on = QPushButton()
        self.tr_set(btn_on, "🟢 הפעל", "🟢 Turn On")
        btn_on.setObjectName("secondaryButton")
        btn_on.clicked.connect(lambda: self.engine.turn_on(self.device.device_id))
        btn_off = QPushButton()
        self.tr_set(btn_off, "🔴 כבה", "🔴 Turn Off")
        btn_off.setObjectName("secondaryButton")
        btn_off.clicked.connect(lambda: self.engine.turn_off(self.device.device_id))
        btn_row.addWidget(btn_on); btn_row.addWidget(btn_off)
        ly.addLayout(btn_row)

        if self.device.states:
            state_combo = QComboBox()
            state_combo.setObjectName("filterCombo")
            for s in self.device.states:
                state_combo.addItem(s.name, s)
            state_row = QHBoxLayout()
            state_row.addWidget(state_combo, 1)
            btn_set_state = QPushButton()
            self.tr_set(btn_set_state, "החל", "Apply")
            btn_set_state.setObjectName("smallButton")
            btn_set_state.clicked.connect(
                lambda: self.engine.set_state(self.device.device_id, state_combo.currentData()))
            state_row.addWidget(btn_set_state)
            ly.addLayout(state_row)

        timed_row = QHBoxLayout()
        self.timed_spin = QSpinBox()
        self.timed_spin.setRange(1, 720)
        self.timed_spin.setValue(self.device.default_timed_minutes)
        self.timed_spin.setSuffix(" " + self.t("דקות", "min"))
        timed_row.addWidget(self.timed_spin, 1)
        btn_timed = QPushButton()
        self.tr_set(btn_timed, "⏱ הפעל לזמן קצוב", "⏱ Timed On")
        btn_timed.setObjectName("primaryButton")
        btn_timed.clicked.connect(
            lambda: self.engine.turn_on_timed(self.device.device_id, self.timed_spin.value()))
        timed_row.addWidget(btn_timed)
        ly.addLayout(timed_row)

    def _update_countdown(self):
        remaining = self.engine.remaining_timed_seconds(self.device.device_id)
        if remaining is None:
            self.countdown_lbl.setText("")
            return
        m, s = divmod(remaining, 60)
        self.countdown_lbl.setText(self.t(
            f"⏱ יכבה אוטומטית בעוד {m:02d}:{s:02d}", f"⏱ Auto-off in {m:02d}:{s:02d}"))


# ─────────────────────────────────────────────────────────
#  Main page
# ─────────────────────────────────────────────────────────
class SmartHomePage(QWidget, Translatable):
    dial_requested = Signal(str)

    def __init__(self, bt_manager, engine: SmartHomeEngine, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.bt = bt_manager
        self.engine = engine
        self.setObjectName("settingsPage")
        self.setLayoutDirection(language_manager.direction)
        self._cards: list[DeviceControlCard] = []
        self._build()
        self._connect_signals()
        self._refresh_devices_list()
        self._refresh_control_panel()
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self.tabs.setLayoutDirection(self._lang_mgr.direction)
        self.retranslate()
        self._refresh_devices_list()
        self._refresh_control_panel()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        from PyQt6.QtWidgets import QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("callTabs")
        outer.addWidget(self.tabs)

        idx0 = self.tabs.addTab(self._build_control_tab(), "")
        self.tr_tab(self.tabs, idx0, "🎛️  לוח בקרה", "🎛️  Control Panel")
        idx1 = self.tabs.addTab(self._build_devices_tab(), "")
        self.tr_tab(self.tabs, idx1, "🔧  ניהול רכיבים", "🔧  Manage Devices")
        idx2 = self.tabs.addTab(self._build_hub_tab(), "")
        self.tr_tab(self.tabs, idx2, "☎️  קו הבית החכם", "☎️  Smart Home Line")

    # ── Control panel tab ─────────────────────────────────

    def _build_control_tab(self) -> QWidget:
        w = QWidget(); ly = QVBoxLayout(w)
        ly.setContentsMargins(16, 12, 16, 12); ly.setSpacing(10)

        info = QLabel()
        self.tr_set(info,
            "חייג לקו הבית החכם ולאחר מכן השתמש בכפתורים למטה לשליחת ההקשות המתאימות בשיחה הפעילה.",
            "Dial the Smart Home line, then use the buttons below to send the right key presses during the active call.")
        info.setObjectName("infoLabel"); info.setWordWrap(True)
        ly.addWidget(info)

        dial_row = QHBoxLayout()
        self.btn_dial_hub = QPushButton()
        self.tr_set(self.btn_dial_hub, "☎️  חייג לקו הבית החכם", "☎️  Call the Smart Home Line")
        self.btn_dial_hub.setObjectName("primaryButton")
        self.btn_dial_hub.setMinimumHeight(44)
        self.btn_dial_hub.clicked.connect(self._dial_hub)
        dial_row.addWidget(self.btn_dial_hub)

        self.btn_announce = QPushButton()
        self.tr_set(self.btn_announce, "🔊 השמע את כל ההכרזות", "🔊 Play All Announcements")
        self.btn_announce.setObjectName("secondaryButton")
        self.btn_announce.setMinimumHeight(44)
        self.btn_announce.clicked.connect(self.engine.announce_all)
        dial_row.addWidget(self.btn_announce)
        ly.addLayout(dial_row)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setObjectName("settingsScroll")
        self.control_container = QWidget()
        self.control_ly = QVBoxLayout(self.control_container)
        self.control_ly.setSpacing(10)
        scroll.setWidget(self.control_container)
        ly.addWidget(scroll, 1)
        return w

    def _dial_hub(self):
        if not self.engine.settings.hub_number:
            QMessageBox.information(self, self.t("שים לב", "Note"),
                self.t("יש להגדיר מספר לקו הבית החכם בלשונית 'קו הבית החכם'",
                       "Please set the Smart Home line number in the 'Smart Home Line' tab"))
            return
        self.dial_requested.emit(self.engine.settings.hub_number)

    def _refresh_control_panel(self):
        while self.control_ly.count():
            item = self.control_ly.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()
        devices = [d for d in self.engine.settings.devices if d.enabled]
        if not devices:
            empty = QLabel()
            self.tr_set(empty, "אין רכיבים מוגדרים עדיין — עבור ללשונית 'ניהול רכיבים' להוספה",
                      "No devices configured yet — go to 'Manage Devices' to add one")
            empty.setObjectName("infoLabel")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.control_ly.addWidget(empty)
        else:
            for device in devices:
                card = DeviceControlCard(device, self.engine, self._lang_mgr)
                self.control_ly.addWidget(card)
                self._cards.append(card)
        self.control_ly.addStretch()

    # ── Devices management tab ────────────────────────────

    def _build_devices_tab(self) -> QWidget:
        w = QWidget(); ly = QVBoxLayout(w)
        ly.setContentsMargins(16, 12, 16, 12); ly.setSpacing(10)

        self.device_list = QListWidget()
        self.device_list.setObjectName("rulesList")
        ly.addWidget(self.device_list, 1)

        btn_row = QHBoxLayout()
        btn_add = QPushButton(); self.tr_set(btn_add, "➕ הוסף רכיב", "➕ Add Device")
        btn_add.setObjectName("primaryButton"); btn_add.clicked.connect(self._add_device)
        btn_edit = QPushButton(); self.tr_set(btn_edit, "✏️ ערוך", "✏️ Edit")
        btn_edit.setObjectName("secondaryButton"); btn_edit.clicked.connect(self._edit_device)
        btn_del = QPushButton(); self.tr_set(btn_del, "🗑 מחק", "🗑 Delete")
        btn_del.setObjectName("secondaryButton"); btn_del.clicked.connect(self._del_device)
        for b in [btn_add, btn_edit, btn_del]: btn_row.addWidget(b)
        btn_row.addStretch(); ly.addLayout(btn_row)

        # ── Nickname recording ──
        nick_group = QGroupBox()
        self.tr_set(nick_group, "🎙️ הכרזה קולית לרכיב הנבחר", "🎙️ Voice Announcement for Selected Device", setter="setTitle")
        nick_group.setObjectName("settingsGroup")
        nly = QVBoxLayout(nick_group)
        self.nick_status = QLabel()
        self.tr_set(self.nick_status, "בחר רכיב מהרשימה", "Select a device from the list")
        self.nick_status.setObjectName("infoLabel")
        nly.addWidget(self.nick_status)
        nick_row = QHBoxLayout()
        btn_record = QPushButton(); self.tr_set(btn_record, "🎙️ הקלט (3 שנ')", "🎙️ Record (3s)")
        btn_record.setObjectName("secondaryButton"); btn_record.clicked.connect(self._record_nickname)
        btn_play = QPushButton(); self.tr_set(btn_play, "▶ נגן", "▶ Play")
        btn_play.setObjectName("secondaryButton"); btn_play.clicked.connect(self._play_nickname)
        nick_row.addWidget(btn_record); nick_row.addWidget(btn_play); nick_row.addStretch()
        nly.addLayout(nick_row)
        ly.addWidget(nick_group)

        return w

    def _refresh_devices_list(self):
        self.device_list.clear()
        for d in self.engine.settings.devices:
            status = "✅" if d.enabled else "⛔"
            has_audio = "🔊" if os.path.exists(self.engine.nickname_path(d.device_id)) else ""
            item = QListWidgetItem(f"{status}  {d.name}   [{self.t('מקש','key')}: {d.key or '—'}]  {has_audio}")
            item.setData(Qt.ItemDataRole.UserRole, d.device_id)
            self.device_list.addItem(item)

    def _add_device(self):
        dlg = DeviceEditorDialog(self._lang_mgr, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.engine.add_device(dlg.get_device())
            self._refresh_devices_list()
            self._refresh_control_panel()

    def _edit_device(self):
        item = self.device_list.currentItem()
        if not item: return
        device = self.engine.get_device(item.data(Qt.ItemDataRole.UserRole))
        if not device: return
        dlg = DeviceEditorDialog(self._lang_mgr, device=device, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.engine.update_device(dlg.get_device())
            self._refresh_devices_list()
            self._refresh_control_panel()

    def _del_device(self):
        item = self.device_list.currentItem()
        if not item: return
        r = QMessageBox.question(self, self.t("מחיקה", "Delete"),
            self.t("למחוק את הרכיב?", "Delete this device?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.engine.remove_device(item.data(Qt.ItemDataRole.UserRole))
            self._refresh_devices_list()
            self._refresh_control_panel()

    def _record_nickname(self):
        item = self.device_list.currentItem()
        if not item:
            return
        device_id = item.data(Qt.ItemDataRole.UserRole)
        self.nick_status.setText(self.t("מקליט… דבר עכשיו", "Recording… speak now"))

        def done(ok, result):
            if ok:
                self.nick_status.setText(self.t("✅ ההכרזה נשמרה", "✅ Announcement saved"))
            else:
                self.nick_status.setText(self.t(f"⚠️ שגיאה: {result}", f"⚠️ Error: {result}"))
            self._refresh_devices_list()

        self.engine.record_nickname(device_id, duration=3.0, callback=done)

    def _play_nickname(self):
        item = self.device_list.currentItem()
        if not item:
            return
        device_id = item.data(Qt.ItemDataRole.UserRole)
        if not self.engine.play_nickname(device_id):
            self.nick_status.setText(self.t("אין הכרזה מוקלטת לרכיב זה", "No announcement recorded for this device"))

    # ── Hub configuration tab ─────────────────────────────

    def _build_hub_tab(self) -> QWidget:
        w = QWidget(); ly = QVBoxLayout(w)
        ly.setContentsMargins(16, 12, 16, 12); ly.setSpacing(14)

        info = QLabel()
        self.tr_set(info,
            "הגדר את המספר של קו הבית החכם (רכיב הבקרה שאליו מתקשרים כדי לשלוט "
            "ברכיבים המחוברים, כגון פיוז חכם בארון החשמל).",
            "Set the phone number of the Smart Home line (the control unit you call "
            "to control connected devices, such as a smart fuse in the electrical panel).")
        info.setObjectName("infoLabel"); info.setWordWrap(True)
        ly.addWidget(info)

        form = QFormLayout(); form.setSpacing(10)
        self.hub_name_edit = QLineEdit()
        form.addRow(self.t("שם הקו:", "Line name:"), self.hub_name_edit)
        self.hub_number_edit = QLineEdit()
        self.hub_number_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        form.addRow(self.t("מספר טלפון:", "Phone number:"), self.hub_number_edit)
        ly.addLayout(form)

        self.chk_announce = QCheckBox()
        self.tr_set(self.chk_announce, "השמע הכרזות אוטומטית כאשר השיחה מתחברת",
                  "Automatically play announcements when the call connects")
        ly.addWidget(self.chk_announce)

        btn_save = QPushButton()
        self.tr_set(btn_save, "💾 שמור", "💾 Save")
        btn_save.setObjectName("primaryButton")
        btn_save.setMinimumHeight(42)
        btn_save.clicked.connect(self._save_hub_settings)
        ly.addWidget(btn_save)
        ly.addStretch()

        self.hub_name_edit.setText(self.engine.settings.hub_name)
        self.hub_number_edit.setText(self.engine.settings.hub_number)
        self.chk_announce.setChecked(self.engine.settings.announce_on_connect)

        return w

    def _save_hub_settings(self):
        self.engine.settings.hub_name = self.hub_name_edit.text().strip() or self.t("בית חכם", "Smart Home")
        self.engine.settings.hub_number = self.hub_number_edit.text().strip()
        self.engine.settings.announce_on_connect = self.chk_announce.isChecked()
        self.engine.save_settings()
        QMessageBox.information(self, self.t("נשמר", "Saved"), self.t("ההגדרות נשמרו", "Settings saved"))

    # ── Signals ────────────────────────────────────────────

    def _connect_signals(self):
        self.engine.status_changed.connect(self._on_status)
        self.engine.sequence_complete.connect(self._on_sequence_complete)
        self.engine.devices_changed.connect(self._refresh_control_panel)

    def _on_status(self, msg: str):
        pass  # surfaced via main_window's status bar connection

    def _on_sequence_complete(self, device_id: str, action: str):
        device = self.engine.get_device(device_id)
        if device:
            self.nick_status.setText(self.t(
                f"✅ {device.name}: {action} בוצע", f"✅ {device.name}: {action} done"))
