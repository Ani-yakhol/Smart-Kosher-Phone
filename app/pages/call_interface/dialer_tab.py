#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""לשונית חיוג"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtGui import QFont

from app.core.language_manager import Translatable


class DialButton(QPushButton):
    def __init__(self, digit, sub="", parent=None):
        super().__init__(parent)
        self.digit = digit
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0,4,0,4); ly.setSpacing(0)
        d = QLabel(digit); d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setObjectName("dialDigit"); ly.addWidget(d)
        if sub:
            s = QLabel(sub); s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.setObjectName("dialSub"); ly.addWidget(s)
        self.setMinimumSize(80,66); self.setMaximumSize(110,76)
        self.setObjectName("dialButton"); self.setCursor(Qt.CursorShape.PointingHandCursor)


class DialerTab(QWidget, Translatable):
    dial_requested = Signal(str)

    def __init__(self, bt_manager, language_manager, rec_manager=None, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.bt  = bt_manager
        self.rec = rec_manager
        self.setObjectName("dialerTab")
        self.setLayoutDirection(language_manager.direction)
        self._build()
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self.retranslate()

    def _build(self):
        ly = QVBoxLayout(self)
        ly.setContentsMargins(24,20,24,20); ly.setSpacing(14)

        title = QLabel()
        title.setObjectName("pageTitle"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tr_set(title, "📞 חיוג", "📞 Dial")
        ly.addWidget(title)

        self.number_display = QLineEdit()
        self.number_display.setObjectName("numberDisplay")
        self.tr_set(self.number_display, "הכנס מספר טלפון", "Enter phone number",
                    setter="setPlaceholderText")
        self.number_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_display.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.number_display.setMinimumHeight(60)
        self.number_display.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.number_display.returnPressed.connect(self._dial)
        ly.addWidget(self.number_display)

        pad = QFrame(); pad.setObjectName("dialPad")
        grid = QGridLayout(pad); grid.setSpacing(10)
        grid.setContentsMargins(12,10,12,10)

        btns = [("1",""),("2","ABC"),("3","DEF"),
                ("4","GHI"),("5","JKL"),("6","MNO"),
                ("7","PQRS"),("8","TUV"),("9","WXYZ"),
                ("*",""),("0","+"),("#","")]
        for i,(d,s) in enumerate(btns):
            r,c = divmod(i,3); c = 2-c
            b = DialButton(d,s)
            b.clicked.connect(lambda _,x=d: self.number_display.insert(x))
            grid.addWidget(b,r,c)
        ly.addWidget(pad)

        row = QHBoxLayout(); row.setSpacing(10)
        for slot, obj in [
            (self._backspace, "actionButton"),
            (self._dial,     "dialCallButton"),
            (lambda: self.number_display.clear(), "actionButton"),
        ]:
            b = QPushButton(); b.setObjectName(obj)
            b.setMinimumHeight(54)
            if obj == "dialCallButton": b.setMinimumWidth(110)
            b.setFont(QFont("Segoe UI Emoji", 20 if obj=="dialCallButton" else 16))
            b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(slot)
            row.addWidget(b)
        self.tr_set(row.itemAt(0).widget(), "⌫", "⌫")
        self.tr_set(row.itemAt(1).widget(), "📞", "📞")
        self.tr_set(row.itemAt(2).widget(), "✕", "✕")
        ly.addLayout(row)
        ly.addStretch()

        hint = QLabel()
        hint.setObjectName("hintLabel"); hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tr_set(hint, "לחיצה ממושכת על 0 תוסיף +  •  Enter לחיוג מהיר",
                    "Long-press 0 to add +  •  Enter to dial quickly")
        ly.addWidget(hint)

    def _backspace(self):
        t = self.number_display.text()
        if t: self.number_display.setText(t[:-1])

    def _dial(self):
        n = self.number_display.text().strip()
        if n: self.dial_requested.emit(n)

    def set_number(self, number: str):
        self.number_display.setText(number)
