#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""דף הגדרות"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QComboBox, QCheckBox,
    QFrame, QGroupBox, QSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class SettingsPage(QWidget):
    def __init__(self, bt_manager, parent=None):
        super().__init__(parent)
        self.bt = bt_manager
        self.setObjectName("settingsPage")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(16)

        title = QLabel("⚙️ הגדרות")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # ── Audio ──
        audio_group = self._group("🔊 שמע")
        audio_layout = QVBoxLayout()

        audio_layout.addWidget(QLabel("עוצמת קול:"))
        vol_row = QHBoxLayout()
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 15)
        self.vol_slider.setValue(10)
        self.vol_slider.setObjectName("settingSlider")
        self.vol_slider.valueChanged.connect(
            lambda v: self.bt.set_volume(v))
        vol_row.addWidget(self.vol_slider)
        self.vol_label = QLabel("10")
        self.vol_label.setFixedWidth(28)
        self.vol_slider.valueChanged.connect(
            lambda v: self.vol_label.setText(str(v)))
        vol_row.addWidget(self.vol_label)
        audio_layout.addLayout(vol_row)

        audio_layout.addWidget(QLabel("עוצמת מיקרופון:"))
        mic_row = QHBoxLayout()
        self.mic_slider = QSlider(Qt.Orientation.Horizontal)
        self.mic_slider.setRange(0, 15)
        self.mic_slider.setValue(10)
        self.mic_slider.setObjectName("settingSlider")
        self.mic_slider.valueChanged.connect(
            lambda v: self.bt.set_mic_volume(v))
        mic_row.addWidget(self.mic_slider)
        self.mic_label = QLabel("10")
        self.mic_label.setFixedWidth(28)
        self.mic_slider.valueChanged.connect(
            lambda v: self.mic_label.setText(str(v)))
        mic_row.addWidget(self.mic_label)
        audio_layout.addLayout(mic_row)

        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)

        # ── Notifications ──
        notif_group = self._group("🔔 התראות")
        notif_layout = QVBoxLayout()

        self.chk_popup = QCheckBox("הצג חלון בשיחה נכנסת")
        self.chk_popup.setChecked(True)
        notif_layout.addWidget(self.chk_popup)

        self.chk_tray = QCheckBox("הצג באזור המגש")
        self.chk_tray.setChecked(True)
        notif_layout.addWidget(self.chk_tray)

        self.chk_sound = QCheckBox("נגן צלצול")
        self.chk_sound.setChecked(True)
        notif_layout.addWidget(self.chk_sound)

        notif_group.setLayout(notif_layout)
        layout.addWidget(notif_group)

        # ── Simulation ──
        sim_group = self._group("🧪 הדגמה")
        sim_layout = QVBoxLayout()

        sim_info = QLabel(
            "מצב הדגמה מאפשר בדיקת הממשק\n"
            "ללא חיבור בלוטוס אמיתי"
        )
        sim_info.setObjectName("infoLabel")
        sim_layout.addWidget(sim_info)

        btn_row = QHBoxLayout()
        btn_sim_call = QPushButton("📲 סמלץ שיחה נכנסת")
        btn_sim_call.setObjectName("secondaryButton")
        btn_sim_call.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_sim_call.clicked.connect(
            lambda: self.bt.simulate_incoming_call("0501234567", "אבא"))
        btn_row.addWidget(btn_sim_call)

        btn_sim_out = QPushButton("📞 סמלץ חיוג")
        btn_sim_out.setObjectName("secondaryButton")
        btn_sim_out.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_sim_out.clicked.connect(
            lambda: self.bt.dial("0521234567"))
        btn_row.addWidget(btn_sim_out)
        sim_layout.addLayout(btn_row)

        sim_group.setLayout(sim_layout)
        layout.addWidget(sim_group)

        # ── About ──
        about_group = self._group("ℹ️ אודות")
        about_layout = QVBoxLayout()
        about_text = QLabel(
            "BluePhone v1.0\n"
            "דיבורית בלוטוס מתקדמת למחשב\n"
            "תומך בפרוטוקול HFP (Hands-Free Profile)\n"
            "פקודות AT לשליטה בפלאפון"
        )
        about_text.setObjectName("aboutText")
        about_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(about_text)
        about_group.setLayout(about_layout)
        layout.addWidget(about_group)

        layout.addStretch()

    def _group(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setObjectName("settingsGroup")
        g.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        return g
