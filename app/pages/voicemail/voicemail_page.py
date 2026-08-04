#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
דף תא קולי — הגדרות מענה, רשימת הודעות, האזנה
"""

import os, uuid
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QListWidget, QListWidgetItem, QGroupBox,
    QCheckBox, QSpinBox, QLineEdit, QComboBox, QTextEdit,
    QFrame, QScrollArea, QMessageBox, QFileDialog, QSizePolicy,
    QDialog, QFormLayout, QDialogButtonBox, QGridLayout
)
from PyQt6.QtCore import Qt, QSize, QUrl
from PyQt6.QtGui import QFont
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.core.voicemail_manager import VoicemailRule, VoicemailManager
from app.core.recording_manager import RecordingEntry, RecordingManager
from app.core.language_manager import Translatable


# ─────────────────────────────────────────────────────────
#  Rule editor dialog
# ─────────────────────────────────────────────────────────
class RuleEditorDialog(QDialog, Translatable):
    DAYS_HE = ["שני","שלישי","רביעי","חמישי","שישי","שבת","ראשון"]
    DAYS_EN = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

    def __init__(self, language_manager, rule: VoicemailRule = None, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.DAYS = self.DAYS_HE if language_manager.is_rtl else self.DAYS_EN
        self.setWindowTitle(self.t("עריכת כלל מענה", "Edit Answer Rule") if rule
                             else self.t("כלל מענה חדש", "New Answer Rule"))
        self.setMinimumWidth(480)
        self.setLayoutDirection(language_manager.direction)
        self._rule = rule
        self._build()
        if rule: self._load(rule)

    def _build(self):
        ly = QVBoxLayout(self); ly.setSpacing(14)

        form = QFormLayout(); form.setSpacing(10)

        self.name_edit = QLineEdit()
        self.tr_set(self.name_edit, "שם הכלל", "Rule name", setter="setPlaceholderText")
        form.addRow(self.t("שם הכלל:", "Rule name:"), self.name_edit)

        self.chk_enabled = QCheckBox()
        self.tr_set(self.chk_enabled, "כלל פעיל", "Rule active")
        self.chk_enabled.setChecked(True)
        form.addRow("", self.chk_enabled)

        self.chk_always = QCheckBox()
        self.tr_set(self.chk_always, "ענה לכל השיחות", "Answer all calls")
        self.chk_always.toggled.connect(self._on_always_toggle)
        form.addRow(self.t("מתי לענות:", "When to answer:"), self.chk_always)

        self.numbers_edit = QTextEdit()
        self.tr_set(self.numbers_edit, "מספרים ספציפיים — מספר אחד בכל שורה",
                    "Specific numbers — one per line", setter="setPlaceholderText")
        self.numbers_edit.setMaximumHeight(80)
        form.addRow(self.t("מספרים:", "Numbers:"), self.numbers_edit)

        # Days checkboxes
        days_frame = QWidget()
        days_ly = QHBoxLayout(days_frame); days_ly.setContentsMargins(0,0,0,0)
        self._day_checks = []
        for d in self.DAYS:
            c = QCheckBox(d); self._day_checks.append(c); days_ly.addWidget(c)
        form.addRow(self.t("ימים:", "Days:"), days_frame)

        # Hours
        hours_frame = QWidget()
        hly = QHBoxLayout(hours_frame); hly.setContentsMargins(0,0,0,0)
        hly.addWidget(QLabel(self.t("משעה", "From hour")))
        self.hour_from = QSpinBox(); self.hour_from.setRange(0,23)
        hly.addWidget(self.hour_from)
        hly.addWidget(QLabel(self.t("עד שעה", "To hour")))
        self.hour_to = QSpinBox(); self.hour_to.setRange(0,23); self.hour_to.setValue(23)
        hly.addWidget(self.hour_to); hly.addStretch()
        form.addRow(self.t("שעות:", "Hours:"), hours_frame)

        self.rings_spin = QSpinBox(); self.rings_spin.setRange(1,15); self.rings_spin.setValue(4)
        form.addRow(self.t("צלצולים לפני מענה:", "Rings before answering:"), self.rings_spin)

        # Greeting
        self.greeting_text = QTextEdit()
        self.tr_set(self.greeting_text, "טקסט הודעת פתיח…", "Greeting message text…",
                    setter="setPlaceholderText")
        self.greeting_text.setMaximumHeight(80)
        form.addRow(self.t("הודעת פתיח:", "Greeting message:"), self.greeting_text)

        # Goodbye
        self.goodbye_text = QTextEdit()
        self.tr_set(self.goodbye_text, "טקסט הודעת סיום…", "Closing message text…",
                    setter="setPlaceholderText")
        self.goodbye_text.setMaximumHeight(60)
        form.addRow(self.t("הודעת סיום:", "Closing message:"), self.goodbye_text)

        self.chk_play_goodbye = QCheckBox()
        self.tr_set(self.chk_play_goodbye, "השמע הודעת סיום לפני ניתוק", "Play closing message before hangup")
        self.chk_play_goodbye.setChecked(True)
        form.addRow("", self.chk_play_goodbye)

        self.max_sec = QSpinBox(); self.max_sec.setRange(10,600); self.max_sec.setValue(120)
        form.addRow(self.t("משך מקסימלי (שניות):", "Maximum length (seconds):"), self.max_sec)

        self.silence_sec = QSpinBox(); self.silence_sec.setRange(2,30); self.silence_sec.setValue(5)
        form.addRow(self.t("ניתוק בשתיקה (שניות):", "Hang up on silence (seconds):"), self.silence_sec)

        ly.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        ly.addWidget(btns)

    def _on_always_toggle(self, checked):
        self.numbers_edit.setEnabled(not checked)
        for c in self._day_checks: c.setEnabled(not checked)
        self.hour_from.setEnabled(not checked)
        self.hour_to.setEnabled(not checked)

    def _load(self, rule: VoicemailRule):
        self.name_edit.setText(rule.name)
        self.chk_enabled.setChecked(rule.enabled)
        self.chk_always.setChecked(rule.answer_always)
        self.numbers_edit.setPlainText("\n".join(rule.answer_numbers))
        for i, c in enumerate(self._day_checks):
            c.setChecked(i in rule.answer_days)
        self.hour_from.setValue(rule.answer_hour_from)
        self.hour_to.setValue(rule.answer_hour_to)
        self.rings_spin.setValue(rule.rings_before_answer)
        self.greeting_text.setPlainText(rule.greeting_text)
        self.goodbye_text.setPlainText(rule.goodbye_text)
        self.chk_play_goodbye.setChecked(rule.play_goodbye)
        self.max_sec.setValue(rule.max_message_sec)
        self.silence_sec.setValue(rule.silence_cutoff_sec)
        self._on_always_toggle(rule.answer_always)

    def get_rule(self) -> VoicemailRule:
        rid = self._rule.rule_id if self._rule else str(uuid.uuid4())[:8]
        numbers = [l.strip() for l in
                   self.numbers_edit.toPlainText().splitlines() if l.strip()]
        days = [i for i,c in enumerate(self._day_checks) if c.isChecked()]
        return VoicemailRule(
            rule_id=rid,
            name=self.name_edit.text() or self.t("כלל חדש", "New rule"),
            enabled=self.chk_enabled.isChecked(),
            answer_always=self.chk_always.isChecked(),
            answer_numbers=numbers,
            answer_days=days,
            answer_hour_from=self.hour_from.value(),
            answer_hour_to=self.hour_to.value(),
            rings_before_answer=self.rings_spin.value(),
            greeting_text=self.greeting_text.toPlainText(),
            goodbye_text=self.goodbye_text.toPlainText(),
            play_goodbye=self.chk_play_goodbye.isChecked(),
            max_message_sec=self.max_sec.value(),
            silence_cutoff_sec=self.silence_sec.value(),
        )


# ─────────────────────────────────────────────────────────
#  Voicemail message item widget
# ─────────────────────────────────────────────────────────
class VoicemailItem(QWidget):
    def __init__(self, entry: RecordingEntry, parent=None):
        super().__init__(parent)
        self.entry = entry
        ly = QHBoxLayout(self); ly.setContentsMargins(10,6,10,6)

        # Unread indicator
        self.dot = QLabel("🔵" if not entry.listened else "✅")
        self.dot.setFixedWidth(24); self.dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(self.dot)

        info = QVBoxLayout()
        top = QHBoxLayout()
        name = entry.name or entry.number
        name_lbl = QLabel(f"📬 {name}")
        name_lbl.setObjectName("vmName")
        name_lbl.setFont(QFont("Segoe UI",11,QFont.Weight.Bold))
        top.addWidget(name_lbl); top.addStretch()
        dur = QLabel(entry.display_duration)
        dur.setObjectName("recDuration"); dur.setFont(QFont("Courier New",10))
        top.addWidget(dur); info.addLayout(top)

        bot = QHBoxLayout()
        num = QLabel(entry.number); num.setObjectName("recNumber")
        num.setFont(QFont("Segoe UI",9)); num.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        bot.addWidget(num); bot.addStretch()
        date = QLabel(entry.display_date)
        date.setObjectName("recDate"); date.setFont(QFont("Segoe UI",9))
        bot.addWidget(date); info.addLayout(bot)
        ly.addLayout(info, 1)


# ─────────────────────────────────────────────────────────
#  Main Voicemail Page
# ─────────────────────────────────────────────────────────
class VoicemailPage(QWidget, Translatable):
    def __init__(self, bt_manager, vm_manager: VoicemailManager,
                 rec_manager: RecordingManager, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.bt  = bt_manager
        self.vm  = vm_manager
        self.rec = rec_manager
        self.setObjectName("voicemailPage")
        self.setLayoutDirection(language_manager.direction)
        self._player: QMediaPlayer = None
        self._audio_out: QAudioOutput = None
        self._build()
        self._connect_signals()
        self._refresh_messages()
        self._refresh_rules()
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self.sub_tabs.setLayoutDirection(self._lang_mgr.direction)
        self.retranslate()
        self._refresh_messages()
        self._refresh_rules()

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)

        # Title bar
        tb = QFrame(); tb.setObjectName("pageHeader")
        tbly = QHBoxLayout(tb); tbly.setContentsMargins(16,10,16,10)
        title = QLabel()
        title.setObjectName("pageTitle")
        title.setFont(QFont("Segoe UI",16,QFont.Weight.Bold))
        self.tr_set(title, "📬 תא קולי", "📬 Voicemail")
        tbly.addWidget(title); tbly.addStretch()
        self.vm_state_lbl = QLabel("")
        self.vm_state_lbl.setObjectName("vmStateLbl")
        self.vm_state_lbl.setFont(QFont("Segoe UI",10))
        tbly.addWidget(self.vm_state_lbl)
        outer.addWidget(tb)

        # Sub tabs
        self.sub_tabs = QTabWidget()
        self.sub_tabs.setObjectName("callTabs")
        self.sub_tabs.setLayoutDirection(self._lang_mgr.direction)
        outer.addWidget(self.sub_tabs, 1)

        idx0 = self.sub_tabs.addTab(self._build_messages_tab(), "")
        self.tr_tab(self.sub_tabs, idx0, "📩  הודעות", "📩  Messages")
        idx1 = self.sub_tabs.addTab(self._build_rules_tab(), "")
        self.tr_tab(self.sub_tabs, idx1, "📋  כללי מענה", "📋  Answer Rules")
        idx2 = self.sub_tabs.addTab(self._build_greetings_tab(), "")
        self.tr_tab(self.sub_tabs, idx2, "🎙️  הודעות פתיח", "🎙️  Greetings")

    # ── Messages tab ─────────────────────────────────────
    def _build_messages_tab(self) -> QWidget:
        w = QWidget(); ly = QVBoxLayout(w)
        ly.setContentsMargins(16,12,16,12); ly.setSpacing(10)

        # Stats row
        sr = QHBoxLayout()
        self.unread_lbl = QLabel()
        self.unread_lbl.setObjectName("vmStats")
        self.unread_lbl.setFont(QFont("Segoe UI",11,QFont.Weight.Bold))
        self.tr_set(self.unread_lbl, "0 הודעות לא נשמעות", "0 unheard messages")
        sr.addWidget(self.unread_lbl); sr.addStretch()
        mark_all = QPushButton()
        self.tr_set(mark_all, "סמן הכל כנשמע", "Mark all as heard")
        mark_all.setObjectName("smallButton")
        mark_all.setCursor(Qt.CursorShape.PointingHandCursor)
        mark_all.clicked.connect(self._mark_all_listened)
        sr.addWidget(mark_all); ly.addLayout(sr)

        # Playback bar
        pb = QFrame(); pb.setObjectName("playbackBar")
        pbly = QHBoxLayout(pb); pbly.setContentsMargins(10,8,10,8)
        self.play_lbl = QLabel()
        self.play_lbl.setObjectName("playLabel"); self.play_lbl.setFont(QFont("Segoe UI",10))
        self.tr_set(self.play_lbl, "לחץ פעמיים על הודעה להאזנה", "Double-click a message to play it")
        pbly.addWidget(self.play_lbl, 1)
        self.btn_play = QPushButton("▶"); self.btn_play.setObjectName("playBtn")
        self.btn_play.setFixedSize(38,38); self.btn_play.setFont(QFont("Segoe UI",16))
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.clicked.connect(self._play_pause); pbly.addWidget(self.btn_play)
        self.btn_stop = QPushButton("⏹"); self.btn_stop.setObjectName("playBtn")
        self.btn_stop.setFixedSize(38,38); self.btn_stop.setFont(QFont("Segoe UI",16))
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self._stop_play); pbly.addWidget(self.btn_stop)
        ly.addWidget(pb)

        self.msg_list = QListWidget()
        self.msg_list.setObjectName("recordingList"); self.msg_list.setSpacing(3)
        self.msg_list.itemDoubleClicked.connect(self._on_msg_double_click)
        ly.addWidget(self.msg_list, 1)

        ar = QHBoxLayout(); ar.setSpacing(10)
        self.btn_del_vm = QPushButton()
        self.tr_set(self.btn_del_vm, "🗑  מחק", "🗑  Delete")
        self.btn_del_vm.setObjectName("secondaryButton")
        self.btn_del_vm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del_vm.clicked.connect(self._delete_vm)
        ar.addWidget(self.btn_del_vm); ar.addStretch()
        btn_folder = QPushButton()
        self.tr_set(btn_folder, "📁  פתח תיקייה", "📁  Open Folder")
        btn_folder.setObjectName("secondaryButton")
        btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_folder.clicked.connect(self._open_vm_folder)
        ar.addWidget(btn_folder); ly.addLayout(ar)
        return w

    # ── Rules tab ────────────────────────────────────────
    def _build_rules_tab(self) -> QWidget:
        w = QWidget(); ly = QVBoxLayout(w)
        ly.setContentsMargins(16,12,16,12); ly.setSpacing(10)

        info = QLabel()
        self.tr_set(info,
            "💡 כללי מענה קובעים מתי ואיך התא הקולי יענה לשיחות.\n"
            "כל כלל יכול להתאים למספרים, ימים ושעות ספציפיים.",
            "💡 Answer rules determine when and how voicemail answers calls.\n"
            "Each rule can target specific numbers, days and hours.")
        info.setObjectName("infoLabel"); info.setWordWrap(True)
        ly.addWidget(info)

        self.rules_list = QListWidget()
        self.rules_list.setObjectName("rulesList"); self.rules_list.setSpacing(3)
        ly.addWidget(self.rules_list, 1)

        br = QHBoxLayout(); br.setSpacing(10)
        btn_add  = QPushButton(); self.tr_set(btn_add, "➕ הוסף כלל", "➕ Add Rule")
        btn_add.setObjectName("primaryButton")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor); btn_add.clicked.connect(self._add_rule)
        btn_edit = QPushButton(); self.tr_set(btn_edit, "✏️ ערוך", "✏️ Edit")
        btn_edit.setObjectName("secondaryButton")
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor); btn_edit.clicked.connect(self._edit_rule)
        btn_del  = QPushButton(); self.tr_set(btn_del, "🗑 מחק", "🗑 Delete")
        btn_del.setObjectName("secondaryButton")
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor);  btn_del.clicked.connect(self._del_rule)
        for b in [btn_add, btn_edit, btn_del]: br.addWidget(b)
        br.addStretch(); ly.addLayout(br)
        return w

    # ── Greetings tab ────────────────────────────────────
    def _build_greetings_tab(self) -> QWidget:
        w = QWidget(); ly = QVBoxLayout(w)
        ly.setContentsMargins(16,12,16,12); ly.setSpacing(10)

        info = QLabel()
        self.tr_set(info,
            "ניתן להקליט הודעות פתיח מותאמות אישית.\n"
            "קבצי WAV יישמרו בתיקיית הודעות הפתיח.",
            "You can record custom greeting messages.\n"
            "WAV files will be saved in the greetings folder.")
        info.setObjectName("infoLabel"); info.setWordWrap(True)
        ly.addWidget(info)

        self.greetings_list = QListWidget()
        self.greetings_list.setObjectName("rulesList")
        ly.addWidget(self.greetings_list, 1)

        gr = QHBoxLayout(); gr.setSpacing(10)
        btn_import = QPushButton()
        self.tr_set(btn_import, "📁 ייבא WAV", "📁 Import WAV")
        btn_import.setObjectName("secondaryButton")
        btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_import.clicked.connect(self._import_greeting)
        btn_play_g = QPushButton()
        self.tr_set(btn_play_g, "▶ נגן", "▶ Play")
        btn_play_g.setObjectName("secondaryButton")
        btn_play_g.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_play_g.clicked.connect(self._play_greeting)
        btn_del_g = QPushButton()
        self.tr_set(btn_del_g, "🗑 מחק", "🗑 Delete")
        btn_del_g.setObjectName("secondaryButton")
        btn_del_g.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del_g.clicked.connect(self._del_greeting)
        for b in [btn_import, btn_play_g, btn_del_g]: gr.addWidget(b)
        gr.addStretch(); ly.addLayout(gr)

        self._refresh_greetings()
        return w

    # ── Signal connections ────────────────────────────────
    def _connect_signals(self):
        self.rec.recordings_changed.connect(self._refresh_messages)
        self.vm.vm_state_changed.connect(self.vm_state_lbl.setText)

    # ── Messages ─────────────────────────────────────────
    def _refresh_messages(self):
        self.msg_list.clear()
        entries = self.rec.get_voicemails()
        unread = sum(1 for e in entries if not e.listened)
        unheard_word = self.t("הודעות לא נשמעות מתוך", "unheard messages out of")
        self.unread_lbl.setText(
            f"{'ℹ️' if unread==0 else '🔵'} {unread} {unheard_word} {len(entries)}")
        for entry in entries:
            item = QListWidgetItem()
            item_w = VoicemailItem(entry)
            item.setSizeHint(QSize(0,62))
            item.setData(Qt.ItemDataRole.UserRole, entry.filename)
            self.msg_list.addItem(item)
            self.msg_list.setItemWidget(item, item_w)

    def _on_msg_double_click(self, item):
        fname = item.data(Qt.ItemDataRole.UserRole)
        path  = self.rec.get_recording_path(fname, voicemail=True)
        self._play_audio(path, fname)
        self.rec.mark_listened(fname, voicemail=True)

    def _mark_all_listened(self):
        for e in self.rec.get_voicemails():
            self.rec.mark_listened(e.filename, voicemail=True)

    def _delete_vm(self):
        item = self.msg_list.currentItem()
        if not item: return
        fname = item.data(Qt.ItemDataRole.UserRole)
        r = QMessageBox.question(self, self.t("מחיקה", "Delete"),
            self.t(f"למחוק את ההודעה {fname}?", f"Delete the message {fname}?"),
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.rec.delete_recording(fname, voicemail=True)

    def _open_vm_folder(self):
        import subprocess
        path = str(self.rec.voicemail_dir)
        os.makedirs(path, exist_ok=True)
        subprocess.Popen(["explorer", path])

    # ── Playback ─────────────────────────────────────────
    def _play_audio(self, path: str, label: str = ""):
        if not os.path.exists(path):
            QMessageBox.warning(self, self.t("שגיאה", "Error"),
                                 self.t("קובץ לא נמצא", "File not found")); return
        if not self._player:
            self._audio_out = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio_out)
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()
        self.play_lbl.setText(self.t("מנגן: ", "Playing: ") + (label or path))
        self.btn_play.setText("⏸")

    def _play_pause(self):
        if not self._player: return
        if self._player.isPlaying():
            self._player.pause(); self.btn_play.setText("▶")
        else:
            self._player.play(); self.btn_play.setText("⏸")

    def _stop_play(self):
        if self._player:
            self._player.stop(); self.btn_play.setText("▶")
            self.play_lbl.setText(self.t("לחץ פעמיים על הודעה להאזנה",
                                           "Double-click a message to play it"))

    # ── Rules ─────────────────────────────────────────────
    def _refresh_rules(self):
        self.rules_list.clear()
        for rule in self.vm.get_rules():
            status = "✅" if rule.enabled else "⛔"
            when = self.t("תמיד", "Always") if rule.answer_always else self.t("מותנה", "Conditional")
            after_word = self.t("אחרי", "after")
            rings_word = self.t("צלצולים", "rings")
            item = QListWidgetItem(f"{status}  {rule.name}  |  {when}  |  "
                                   f"{after_word} {rule.rings_before_answer} {rings_word}")
            item.setData(Qt.ItemDataRole.UserRole, rule.rule_id)
            self.rules_list.addItem(item)

    def _add_rule(self):
        dlg = RuleEditorDialog(self._lang_mgr, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.vm.add_rule(dlg.get_rule())
            self._refresh_rules()

    def _edit_rule(self):
        item = self.rules_list.currentItem()
        if not item: return
        rid = item.data(Qt.ItemDataRole.UserRole)
        rule = next((r for r in self.vm.get_rules() if r.rule_id==rid), None)
        if not rule: return
        dlg = RuleEditorDialog(self._lang_mgr, rule=rule, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.vm.update_rule(dlg.get_rule())
            self._refresh_rules()

    def _del_rule(self):
        item = self.rules_list.currentItem()
        if not item: return
        rid = item.data(Qt.ItemDataRole.UserRole)
        r = QMessageBox.question(self, self.t("מחיקה", "Delete"),
            self.t("למחוק את הכלל?", "Delete this rule?"),
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.vm.delete_rule(rid); self._refresh_rules()

    # ── Greetings ─────────────────────────────────────────
    def _refresh_greetings(self):
        self.greetings_list.clear()
        for f in self.vm.list_greeting_files():
            self.greetings_list.addItem(f)

    def _import_greeting(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.t("בחר קובץ WAV", "Select WAV File"), "", "WAV Files (*.wav)")
        if not path: return
        import shutil
        dest = os.path.join(self.vm.get_greetings_dir(),
                            os.path.basename(path))
        shutil.copy2(path, dest)
        self._refresh_greetings()

    def _play_greeting(self):
        item = self.greetings_list.currentItem()
        if not item: return
        path = os.path.join(self.vm.get_greetings_dir(), item.text())
        self._play_audio(path, item.text())

    def _del_greeting(self):
        item = self.greetings_list.currentItem()
        if not item: return
        path = os.path.join(self.vm.get_greetings_dir(), item.text())
        r = QMessageBox.question(self, self.t("מחיקה", "Delete"),
            self.t(f"למחוק {item.text()}?", f"Delete {item.text()}?"),
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            try: os.remove(path)
            except: pass
            self._refresh_greetings()
