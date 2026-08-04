#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""שורת סטטוס עליונה — כולל כפתור ערכת נושא ותצוגת שפה"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtGui import QFont
from typing import Optional
from app.bluetooth_manager import BluetoothDevice
from app.core.language_manager import Translatable


class StatusBarWidget(QWidget, Translatable):
    theme_toggle_requested = Signal()

    def __init__(self, bt_manager, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.bt = bt_manager
        self.setObjectName("statusBar")
        self.setFixedHeight(48)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)  # always LTR for this bar

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 14, 4)
        layout.setSpacing(12)

        # BT connection status (left)
        self.bt_icon = QLabel("●")
        self.bt_icon.setObjectName("btDot")
        self.bt_icon.setFont(QFont("Segoe UI", 14))
        layout.addWidget(self.bt_icon)

        self.bt_label = QLabel()
        self.bt_label.setObjectName("btStatus")
        self.bt_label.setFont(QFont("Segoe UI", 9))
        self.tr_set(self.bt_label, "לא מחובר", "Not connected")
        layout.addWidget(self.bt_label)

        # Demo / simulation-mode badge — hidden unless actually simulating
        self.sim_badge = QLabel()
        self.sim_badge.setObjectName("simBadge")
        self.sim_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.tr_set(self.sim_badge, "מצב הדגמה", "Demo mode")
        self.sim_badge.setVisible(False)
        layout.addWidget(self.sim_badge)

        # Status message (centre)
        layout.addStretch()

        self.msg_label = QLabel("")
        self.msg_label.setObjectName("statusMsg")
        self.msg_label.setFont(QFont("Segoe UI", 9))
        self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.msg_label)

        layout.addStretch()

        # Theme toggle button (right)
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("themeToggleBtnBar")
        self.btn_theme.setFixedHeight(30)
        self.btn_theme.setMinimumWidth(100)
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.setFont(QFont("Segoe UI", 9))
        self.tr_set(self.btn_theme, "🌙  מצב כהה", "🌙  Dark Mode")
        self.btn_theme.clicked.connect(self.theme_toggle_requested)
        layout.addWidget(self.btn_theme)

        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(lambda: self.msg_label.setText(""))

        self._is_dark = False
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.retranslate()
        self.set_theme_label("dark" if self._is_dark else "light")
        self.set_device(self.bt.current_device if self.bt.is_connected else None)

    def set_device(self, device: Optional[BluetoothDevice]):
        if device:
            self.bt_icon.setObjectName("btDotConnected")
            self.bt_icon.style().unpolish(self.bt_icon)
            self.bt_icon.style().polish(self.bt_icon)
            self.bt_label.setText(device.name[:24])
            self.sim_badge.setVisible(bool(self.bt.simulation_mode))
        else:
            self.bt_icon.setObjectName("btDot")
            self.bt_icon.style().unpolish(self.bt_icon)
            self.bt_icon.style().polish(self.bt_icon)
            self.tr_set(self.bt_label, "לא מחובר", "Not connected")
            self.sim_badge.setVisible(False)

    def set_message(self, msg: str):
        self.msg_label.setText(msg)
        self._clear_timer.start(4000)

    def set_theme_label(self, theme: str):
        self._is_dark = (theme == "dark")
        if self._is_dark:
            self.tr_set(self.btn_theme, "☀️  מצב בהיר", "☀️  Light Mode")
        else:
            self.tr_set(self.btn_theme, "🌙  מצב כהה", "🌙  Dark Mode")
