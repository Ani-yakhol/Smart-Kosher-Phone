#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""סרגל ניווט תחתון"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtGui import QFont


class NavButton(QPushButton):
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.setText(f"{icon}\n{label}")
        self.setObjectName("navButton")
        self.setCheckable(True)
        self.setMinimumHeight(64)
        self.setFont(QFont("Segoe UI", 9))
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class NavBar(QWidget):
    home_clicked = Signal()
    devices_clicked = Signal()
    contacts_clicked = Signal()
    settings_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("navBar")
        self.setFixedHeight(70)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.btn_home = NavButton("📞", "חיוג")
        self.btn_contacts = NavButton("👥", "אנשי קשר")
        self.btn_devices = NavButton("📡", "מכשירים")
        self.btn_settings = NavButton("⚙️", "הגדרות")

        layout.addWidget(self.btn_home)
        layout.addWidget(self.btn_contacts)
        layout.addWidget(self.btn_devices)
        layout.addWidget(self.btn_settings)

        self.btn_home.clicked.connect(self.home_clicked)
        self.btn_contacts.clicked.connect(self.contacts_clicked)
        self.btn_devices.clicked.connect(self.devices_clicked)
        self.btn_settings.clicked.connect(self.settings_clicked)

        self._buttons = [self.btn_home, self.btn_contacts,
                         self.btn_devices, self.btn_settings]

        # Map page indices to buttons
        self._page_map = {0: 0, 3: 2, 4: 1, 5: 3}

        self.set_active(0)

    def set_active(self, page_index: int):
        btn_idx = self._page_map.get(page_index, -1)
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == btn_idx)
