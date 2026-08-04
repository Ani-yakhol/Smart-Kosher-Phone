#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""לשונית יומן שיחות — תת-לשוניות לסינון"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QTabWidget, QFrame, QMessageBox, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal as Signal
from PyQt6.QtGui import QFont

from app.core.call_log import CallLog, CallLogEntry
from app.core.language_manager import Translatable


class CallLogItem(QWidget, Translatable):
    def __init__(self, entry: CallLogEntry, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.entry = entry
        is_rtl = language_manager.is_rtl
        ly = QHBoxLayout(self)
        ly.setContentsMargins(10, 6, 10, 6)
        ly.setSpacing(10)

        icon_lbl = QLabel(entry.direction_icon)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 20))
        icon_lbl.setFixedWidth(32)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(icon_lbl)

        info = QVBoxLayout(); info.setSpacing(2)
        top = QHBoxLayout()
        display = entry.name if entry.name else entry.number

        COLORS_LIGHT = {
            "incoming":"#1565C0","outgoing":"#2E7D32",
            "missed":"#C62828","rejected":"#E65100","blacklist":"#6A1B9A",
        }
        name_lbl = QLabel(display)
        name_lbl.setObjectName("logName")
        name_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        name_lbl.setStyleSheet(
            f"color:{COLORS_LIGHT.get(entry.direction,'#333333')};")
        top.addWidget(name_lbl); top.addStretch()
        dur_lbl = QLabel(entry.display_duration)
        dur_lbl.setObjectName("logDuration")
        dur_lbl.setFont(QFont("Courier New", 9))
        top.addWidget(dur_lbl)
        info.addLayout(top)

        bot = QHBoxLayout()
        num_lbl = QLabel(entry.number)
        num_lbl.setObjectName("logNumber")
        num_lbl.setFont(QFont("Segoe UI", 9))
        num_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        bot.addWidget(num_lbl)
        dir_lbl = QLabel(f"  •  {entry.direction_label_for(is_rtl)}")
        dir_lbl.setObjectName("logDirLabel")
        dir_lbl.setFont(QFont("Segoe UI", 9))
        bot.addWidget(dir_lbl)
        bot.addStretch()
        date_lbl = QLabel(entry.display_date_for(is_rtl))
        date_lbl.setObjectName("logDate")
        date_lbl.setFont(QFont("Segoe UI", 9))
        bot.addWidget(date_lbl)
        info.addLayout(bot)
        ly.addLayout(info, 1)

        self.dial_btn = QPushButton("📞")
        self.dial_btn.setObjectName("contactDialBtn")
        self.dial_btn.setFixedSize(34, 34)
        self.dial_btn.setFont(QFont("Segoe UI Emoji", 14))
        self.dial_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tr_set(self.dial_btn, "חייג בחזרה", "Call back", setter="setToolTip")
        ly.addWidget(self.dial_btn)


class LogListWidget(QWidget, Translatable):
    """רשימת שיחות לפי סינון"""
    dial_requested = Signal(str)

    def __init__(self, call_log: CallLog, language_manager, direction: str = "", parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self._log = call_log
        self._direction = direction
        self.setLayoutDirection(language_manager.direction)
        ly = QVBoxLayout(self)
        ly.setContentsMargins(10, 8, 10, 8)
        ly.setSpacing(6)

        self._count_lbl = QLabel("")
        self._count_lbl.setObjectName("logStats")
        self._count_lbl.setFont(QFont("Segoe UI", 9))
        ly.addWidget(self._count_lbl)

        self._list = QListWidget()
        self._list.setObjectName("callLogList")
        self._list.setSpacing(2)
        ly.addWidget(self._list, 1)

        ar = QHBoxLayout()
        self._btn_clear = QPushButton()
        self.tr_set(self._btn_clear, "🗑  נקה", "🗑  Clear")
        self._btn_clear.setObjectName("secondaryButton")
        self._btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear.clicked.connect(self._clear)
        ar.addWidget(self._btn_clear); ar.addStretch()
        self._btn_bl = QPushButton()
        self.tr_set(self._btn_bl, "⛔  חסום מספר", "⛔  Block Number")
        self._btn_bl.setObjectName("secondaryButton")
        self._btn_bl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_bl.clicked.connect(self._blacklist_selected)
        ar.addWidget(self._btn_bl)
        ly.addLayout(ar)

    def retranslate(self):
        super().retranslate()
        self.setLayoutDirection(self._lang_mgr.direction)
        self.refresh()

    def refresh(self):
        entries = self._log.get_filtered(self._direction)
        self._list.clear()
        for entry in entries:
            item = QListWidgetItem()
            w = CallLogItem(entry, self._lang_mgr)
            w.dial_btn.clicked.connect(
                lambda _, n=entry.number: self.dial_requested.emit(n))
            item.setSizeHint(QSize(0, 62))
            self._list.addItem(item)
            self._list.setItemWidget(item, w)
        total = len(entries)
        label = self.t(
            {"": "כל השיחות", "incoming": "נכנסות", "outgoing": "יוצאות",
             "missed": "לא נענו", "rejected": "נדחו", "blacklist": "חסומות"}.get(self._direction, ""),
            {"": "All Calls", "incoming": "Incoming", "outgoing": "Outgoing",
             "missed": "Missed", "rejected": "Declined", "blacklist": "Blocked"}.get(self._direction, ""))
        calls_word = self.t("שיחות", "calls")
        self._count_lbl.setText(f"{label}: {total} {calls_word}")

    def _clear(self):
        r = QMessageBox.question(
            self, self.t("נקה", "Clear"), self.t("למחוק רשומות אלו?", "Delete these entries?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self._log.clear()
            self.refresh()

    def _blacklist_selected(self):
        item = self._list.currentItem()
        if item:
            w = self._list.itemWidget(item)
            if w and hasattr(w, 'entry'):
                self._log.add_to_blacklist(w.entry.number)
                self.refresh()


class CallLogTab(QWidget, Translatable):
    dial_requested = Signal(str)

    def __init__(self, call_log: CallLog, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self._log = call_log
        self.setObjectName("callLogTab")
        self.setLayoutDirection(language_manager.direction)
        self._sub_lists: list[LogListWidget] = []
        self._build(language_manager)
        self._connect()
        self._refresh()
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self._filter_tabs.setLayoutDirection(self._lang_mgr.direction)
        self.retranslate()
        for w in self._sub_lists:
            w.retranslate()
        self._refresh()

    def _build(self, language_manager):
        ly = QVBoxLayout(self)
        ly.setContentsMargins(10, 10, 10, 10)
        ly.setSpacing(8)

        # Header
        hr = QHBoxLayout()
        title = QLabel()
        title.setObjectName("pageTitle")
        self.tr_set(title, "📋  יומן שיחות", "📋  Call Log")
        hr.addWidget(title); hr.addStretch()
        self._stats_lbl = QLabel("")
        self._stats_lbl.setObjectName("logStats")
        hr.addWidget(self._stats_lbl)
        ly.addLayout(hr)

        # Sub-tabs for filtering
        self._filter_tabs = QTabWidget()
        self._filter_tabs.setObjectName("subTabsNorth")
        self._filter_tabs.setLayoutDirection(language_manager.direction)
        self._filter_tabs.setTabPosition(QTabWidget.TabPosition.North)

        filters = [
            ("📋  הכל", "📋  All",              ""),
            ("📲  נכנסות", "📲  Incoming",       "incoming"),
            ("📞  יוצאות", "📞  Outgoing",       "outgoing"),
            ("📵  לא נענו", "📵  Missed",        "missed"),
            ("🚫  נדחו", "🚫  Declined",         "rejected"),
            ("⛔  חסומות", "⛔  Blocked",         "blacklist"),
        ]
        for he, en, direction in filters:
            w = LogListWidget(self._log, language_manager, direction)
            w.dial_requested.connect(self.dial_requested)
            idx = self._filter_tabs.addTab(w, "")
            self.tr_tab(self._filter_tabs, idx, he, en)
            self._sub_lists.append(w)

        ly.addWidget(self._filter_tabs, 1)

        # Blacklist manager section
        bl_frame = QFrame(); bl_frame.setObjectName("blacklistFrame")
        bly = QVBoxLayout(bl_frame)
        bly.setContentsMargins(10, 8, 10, 8); bly.setSpacing(6)
        bl_title = QLabel()
        bl_title.setObjectName("sectionLabel")
        self.tr_set(bl_title, "⛔  רשימה שחורה — הוסף מספר ידנית",
                    "⛔  Blacklist — add a number manually")
        bly.addWidget(bl_title)
        bl_row = QHBoxLayout()
        self._bl_input = QLineEdit()
        self._bl_input.setObjectName("searchInput")
        self.tr_set(self._bl_input, "מספר לחסימה…", "Number to block…", setter="setPlaceholderText")
        self._bl_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        bl_row.addWidget(self._bl_input)
        btn_add = QPushButton()
        self.tr_set(btn_add, "חסום", "Block")
        btn_add.setObjectName("smallButton")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._add_bl_manual)
        bl_row.addWidget(btn_add)
        bly.addLayout(bl_row)
        ly.addWidget(bl_frame)

    def _connect(self):
        self._log.log_updated.connect(self._refresh)
        self._filter_tabs.currentChanged.connect(lambda _: self._refresh())

    def _refresh(self):
        for w in self._sub_lists:
            w.refresh()
        all_e = self._log.get_all()
        missed = sum(1 for e in all_e if e.direction == "missed")
        total_word = self.t("סה״כ", "Total")
        missed_word = self.t("לא נענו", "missed")
        self._stats_lbl.setText(f"{total_word} {len(all_e)}  •  {missed} {missed_word}")

    def _add_bl_manual(self):
        n = self._bl_input.text().strip()
        if n:
            self._log.add_to_blacklist(n)
            self._bl_input.clear()
            self._refresh()
