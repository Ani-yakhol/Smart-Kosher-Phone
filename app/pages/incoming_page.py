#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""דף שיחה נכנסת"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QFont

from app.bluetooth_manager import CallInfo


class IncomingCallPage(QWidget):
    answered = Signal()
    rejected = Signal()

    def __init__(self, bt_manager, parent=None):
        super().__init__(parent)
        self.bt = bt_manager
        self.setObjectName("incomingPage")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_state = False
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 60, 30, 60)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Incoming label
        incoming_lbl = QLabel("📲 שיחה נכנסת")
        incoming_lbl.setObjectName("incomingLabel")
        incoming_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        incoming_lbl.setFont(QFont("Segoe UI", 16))
        layout.addWidget(incoming_lbl)

        layout.addSpacing(20)

        # Avatar
        self.avatar = QLabel("👤")
        self.avatar.setObjectName("incomingAvatar")
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setFont(QFont("Segoe UI Emoji", 72))
        layout.addWidget(self.avatar)

        layout.addSpacing(16)

        # Name
        self.name_label = QLabel("")
        self.name_label.setObjectName("incomingName")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        layout.addWidget(self.name_label)

        # Number
        self.number_label = QLabel("")
        self.number_label.setObjectName("incomingNumber")
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setFont(QFont("Segoe UI", 16))
        self.number_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        layout.addWidget(self.number_label)

        layout.addStretch()

        # Pulse ring effect label
        self.ring_label = QLabel("〜 〜 〜")
        self.ring_label.setObjectName("ringLabel")
        self.ring_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ring_label.setFont(QFont("Segoe UI", 20))
        layout.addWidget(self.ring_label)

        layout.addStretch()

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(40)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Reject
        self.btn_reject = QPushButton("📵")
        self.btn_reject.setObjectName("rejectButton")
        self.btn_reject.setFixedSize(90, 90)
        self.btn_reject.setFont(QFont("Segoe UI Emoji", 34))
        self.btn_reject.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reject.setToolTip("דחה שיחה")
        self.btn_reject.clicked.connect(self._on_reject)

        # Answer
        self.btn_answer = QPushButton("📞")
        self.btn_answer.setObjectName("answerButton")
        self.btn_answer.setFixedSize(90, 90)
        self.btn_answer.setFont(QFont("Segoe UI Emoji", 34))
        self.btn_answer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_answer.setToolTip("ענה לשיחה")
        self.btn_answer.clicked.connect(self._on_answer)

        # RTL: answer on right, reject on left
        btn_row.addWidget(self.btn_reject)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_answer)
        layout.addLayout(btn_row)

        # Labels under buttons
        lbl_row = QHBoxLayout()
        lbl_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_row.addWidget(self._small_label("דחה"))
        lbl_row.addStretch()
        lbl_row.addWidget(self._small_label("ענה"))
        layout.addLayout(lbl_row)

    def _small_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("btnLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFont(QFont("Segoe UI", 11))
        return lbl

    def show_incoming(self, call_info: CallInfo):
        name = call_info.name or ""
        number = call_info.number

        if name:
            self.name_label.setText(name)
            self.number_label.setText(number)
        else:
            self.name_label.setText(number)
            self.number_label.setText("")

        self._pulse_timer.start(600)

    def _pulse(self):
        self._pulse_state = not self._pulse_state
        if self._pulse_state:
            self.ring_label.setText("〜  〜  〜")
        else:
            self.ring_label.setText("  〜  〜  ")

    def _on_answer(self):
        self._pulse_timer.stop()
        self.answered.emit()

    def _on_reject(self):
        self._pulse_timer.stop()
        self.rejected.emit()
