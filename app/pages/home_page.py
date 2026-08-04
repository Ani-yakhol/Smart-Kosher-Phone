#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""דף בית - חיוג"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QSize
from PyQt6.QtGui import QFont, QColor


class DialButton(QPushButton):
    def __init__(self, digit: str, sub: str = "", parent=None):
        super().__init__(parent)
        self.digit = digit
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        lbl_main = QLabel(digit)
        lbl_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_main.setObjectName("dialDigit")
        layout.addWidget(lbl_main)

        if sub:
            lbl_sub = QLabel(sub)
            lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_sub.setObjectName("dialSub")
            layout.addWidget(lbl_sub)

        self.setMinimumSize(80, 70)
        self.setMaximumSize(110, 80)
        self.setObjectName("dialButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class HomePage(QWidget):
    dial_requested = Signal(str)

    def __init__(self, bt_manager, parent=None):
        super().__init__(parent)
        self.bt = bt_manager
        self.setObjectName("homePage")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("📞 חיוג")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Number display
        self.number_display = QLineEdit()
        self.number_display.setObjectName("numberDisplay")
        self.number_display.setPlaceholderText("הכנס מספר טלפון")
        self.number_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_display.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.number_display.setMinimumHeight(64)
        font = QFont("Segoe UI", 24, QFont.Weight.Bold)
        self.number_display.setFont(font)
        layout.addWidget(self.number_display)

        # Dialpad
        pad_frame = QFrame()
        pad_frame.setObjectName("dialPad")
        pad_layout = QGridLayout(pad_frame)
        pad_layout.setSpacing(10)
        pad_layout.setContentsMargins(10, 10, 10, 10)

        buttons = [
            ("1", ""),   ("2", "ABC"), ("3", "DEF"),
            ("4", "GHI"), ("5", "JKL"), ("6", "MNO"),
            ("7", "PQRS"), ("8", "TUV"), ("9", "WXYZ"),
            ("*", ""),   ("0", "+"),   ("#", ""),
        ]

        self._dial_buttons = []
        for i, (digit, sub) in enumerate(buttons):
            row, col = divmod(i, 3)
            # RTL: reverse columns
            col = 2 - col
            btn = DialButton(digit, sub)
            btn.clicked.connect(lambda _, d=digit: self._on_digit(d))
            pad_layout.addWidget(btn, row, col)
            self._dial_buttons.append(btn)

        layout.addWidget(pad_frame)

        # Action row: Backspace + Dial + Clear
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)

        self.btn_backspace = QPushButton("⌫")
        self.btn_backspace.setObjectName("actionButton")
        self.btn_backspace.setMinimumHeight(56)
        self.btn_backspace.setFont(QFont("Segoe UI", 18))
        self.btn_backspace.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_backspace.clicked.connect(self._backspace)
        action_layout.addWidget(self.btn_backspace)

        self.btn_dial = QPushButton("📞")
        self.btn_dial.setObjectName("dialCallButton")
        self.btn_dial.setMinimumHeight(56)
        self.btn_dial.setMinimumWidth(120)
        self.btn_dial.setFont(QFont("Segoe UI", 24))
        self.btn_dial.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dial.clicked.connect(self._dial)
        action_layout.addWidget(self.btn_dial)

        self.btn_clear = QPushButton("✕")
        self.btn_clear.setObjectName("actionButton")
        self.btn_clear.setMinimumHeight(56)
        self.btn_clear.setFont(QFont("Segoe UI", 16))
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(lambda: self.number_display.clear())
        action_layout.addWidget(self.btn_clear)

        layout.addLayout(action_layout)
        layout.addStretch()

        # Quick dial hint
        hint = QLabel("לחיצה ממושכת על 0 תוסיף +")
        hint.setObjectName("hintLabel")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Keyboard shortcut: Enter to dial
        self.number_display.returnPressed.connect(self._dial)

    def _on_digit(self, digit: str):
        self.number_display.insert(digit)

    def _backspace(self):
        text = self.number_display.text()
        if text:
            self.number_display.setText(text[:-1])

    def _dial(self):
        number = self.number_display.text().strip()
        if number:
            self.dial_requested.emit(number)
