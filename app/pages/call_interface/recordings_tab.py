#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""לשונית הקלטות שיחות"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QFrame, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, QUrl
from PyQt6.QtGui import QFont
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from app.core.recording_manager import RecordingEntry
from app.core.language_manager import Translatable


class RecordingItem(QWidget):
    def __init__(self, entry: RecordingEntry, parent=None):
        super().__init__(parent)
        self.entry = entry
        ly = QHBoxLayout(self); ly.setContentsMargins(10,6,10,6)

        # Unread dot
        dot = QLabel("🔵" if not entry.listened else "")
        dot.setFixedWidth(20); dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(dot)

        info = QVBoxLayout()
        top = QHBoxLayout()
        name = entry.name or entry.number
        direction_icon = "📲" if entry.direction=="incoming" else "📞"
        name_lbl = QLabel(f"{direction_icon} {name}")
        name_lbl.setObjectName("recName")
        name_lbl.setFont(QFont("Segoe UI",11,QFont.Weight.Bold))
        top.addWidget(name_lbl)
        top.addStretch()
        dur_lbl = QLabel(entry.display_duration)
        dur_lbl.setObjectName("recDuration")
        dur_lbl.setFont(QFont("Courier New",10))
        top.addWidget(dur_lbl)
        info.addLayout(top)

        bot = QHBoxLayout()
        num_lbl = QLabel(entry.number)
        num_lbl.setObjectName("recNumber")
        num_lbl.setFont(QFont("Segoe UI",9))
        num_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        bot.addWidget(num_lbl)
        bot.addStretch()
        date_lbl = QLabel(entry.display_date)
        date_lbl.setObjectName("recDate")
        date_lbl.setFont(QFont("Segoe UI",9))
        bot.addWidget(date_lbl)
        info.addLayout(bot)

        ly.addLayout(info, 1)


class RecordingsTab(QWidget, Translatable):
    def __init__(self, rec_manager, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.rec = rec_manager
        self.setObjectName("recordingsTab")
        self.setLayoutDirection(language_manager.direction)
        self._player: QMediaPlayer = None
        self._audio_out: QAudioOutput = None
        self._build()
        self._connect_signals()
        self._refresh()
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self.retranslate()
        self._refresh()

    def _build(self):
        ly = QVBoxLayout(self); ly.setContentsMargins(16,16,16,16); ly.setSpacing(12)

        # Title row
        tr = QHBoxLayout()
        title = QLabel()
        title.setObjectName("pageTitle")
        self.tr_set(title, "⏺ הקלטות שיחות", "⏺ Call Recordings")
        tr.addWidget(title); tr.addStretch()
        self.rec_badge = QLabel("")
        self.rec_badge.setObjectName("recBadge")
        tr.addWidget(self.rec_badge)
        ly.addLayout(tr)

        # Playback bar
        pb = QFrame(); pb.setObjectName("playbackBar")
        pbly = QHBoxLayout(pb); pbly.setContentsMargins(10,8,10,8)
        self.play_lbl = QLabel()
        self.play_lbl.setObjectName("playLabel")
        self.play_lbl.setFont(QFont("Segoe UI",10))
        self.tr_set(self.play_lbl, "בחר הקלטה להאזנה", "Select a recording to play")
        pbly.addWidget(self.play_lbl, 1)

        self.btn_play  = QPushButton("▶")
        self.btn_play.setObjectName("playBtn")
        self.btn_play.setFixedSize(38,38)
        self.btn_play.setFont(QFont("Segoe UI",16))
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.clicked.connect(self._play_pause)
        pbly.addWidget(self.btn_play)

        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setObjectName("playBtn")
        self.btn_stop.setFixedSize(38,38)
        self.btn_stop.setFont(QFont("Segoe UI",16))
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self._stop)
        pbly.addWidget(self.btn_stop)
        ly.addWidget(pb)

        # List
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("recordingList")
        self.list_widget.setSpacing(3)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        ly.addWidget(self.list_widget, 1)

        # Action row
        ar = QHBoxLayout(); ar.setSpacing(10)
        self.btn_delete = QPushButton()
        self.tr_set(self.btn_delete, "🗑  מחק", "🗑  Delete")
        self.btn_delete.setObjectName("secondaryButton")
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.clicked.connect(self._delete_selected)
        ar.addWidget(self.btn_delete)
        ar.addStretch()
        self.btn_open_folder = QPushButton()
        self.tr_set(self.btn_open_folder, "📁  פתח תיקייה", "📁  Open Folder")
        self.btn_open_folder.setObjectName("secondaryButton")
        self.btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self._open_folder)
        ar.addWidget(self.btn_open_folder)
        ly.addLayout(ar)

    def _connect_signals(self):
        self.rec.recordings_changed.connect(self._refresh)

    def _refresh(self):
        self.list_widget.clear()
        entries = self.rec.get_recordings()
        for entry in entries:
            item = QListWidgetItem()
            w = RecordingItem(entry)
            item.setSizeHint(QSize(0, 64))
            item.setData(Qt.ItemDataRole.UserRole, entry.filename)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, w)
        self.rec_badge.setText(f"{len(entries)} " + self.t("הקלטות", "recordings"))

    def _on_double_click(self, item):
        filename = item.data(Qt.ItemDataRole.UserRole)
        self._play_file(filename, voicemail=False)
        self.rec.mark_listened(filename, voicemail=False)
        self._refresh()

    def _play_file(self, filename: str, voicemail=False):
        path = self.rec.get_recording_path(filename, voicemail)
        if not os.path.exists(path):
            QMessageBox.warning(self, self.t("שגיאה", "Error"),
                                 self.t("קובץ ההקלטה לא נמצא", "Recording file not found"))
            return
        if not self._player:
            self._audio_out = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio_out)
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()
        self.play_lbl.setText(self.t("מנגן: ", "Playing: ") + filename)
        self.btn_play.setText("⏸")

    def _play_pause(self):
        if not self._player: return
        if self._player.isPlaying():
            self._player.pause(); self.btn_play.setText("▶")
        else:
            self._player.play(); self.btn_play.setText("⏸")

    def _stop(self):
        if self._player:
            self._player.stop(); self.btn_play.setText("▶")
            self.play_lbl.setText(self.t("בחר הקלטה להאזנה", "Select a recording to play"))

    def _delete_selected(self):
        item = self.list_widget.currentItem()
        if not item: return
        filename = item.data(Qt.ItemDataRole.UserRole)
        r = QMessageBox.question(self, self.t("מחיקה", "Delete"),
            self.t(f"למחוק את ההקלטה {filename}?", f"Delete the recording {filename}?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.rec.delete_recording(filename, voicemail=False)

    def _open_folder(self):
        import subprocess
        path = str(self.rec.base_dir)
        os.makedirs(path, exist_ok=True)
        subprocess.Popen(["explorer", path])
