#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""דף שיחה פעילה"""

import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer
from PyQt6.QtGui import QFont

from app.bluetooth_manager import CallInfo


class CallPage(QWidget):
    hangup_requested = Signal()

    def __init__(self, bt_manager, parent=None):
        super().__init__(parent)
        self.bt = bt_manager
        self.setObjectName("callPage")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._start_time: float = 0
        self._active = False
        self._show_dtmf = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 30, 20, 20)
        layout.setSpacing(0)

        # ── Avatar circle ──
        avatar_container = QWidget()
        avatar_container.setFixedHeight(130)
        avatar_layout = QVBoxLayout(avatar_container)
        avatar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label = QLabel("👤")
        self.avatar_label.setObjectName("callAvatar")
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setFont(QFont("Segoe UI Emoji", 52))
        avatar_layout.addWidget(self.avatar_label)
        layout.addWidget(avatar_container)

        layout.addSpacing(12)

        # ── Name ──
        self.name_label = QLabel("")
        self.name_label.setObjectName("callName")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        layout.addWidget(self.name_label)

        # ── Number ──
        self.number_label = QLabel("")
        self.number_label.setObjectName("callNumber")
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setFont(QFont("Segoe UI", 15))
        self.number_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        layout.addWidget(self.number_label)

        layout.addSpacing(8)

        # ── Status / Timer ──
        self.status_label = QLabel("מחייג...")
        self.status_label.setObjectName("callStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Segoe UI", 13))
        layout.addWidget(self.status_label)

        self.timer_label = QLabel("00:00")
        self.timer_label.setObjectName("callTimer")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setFont(QFont("Courier New", 32, QFont.Weight.Bold))
        layout.addWidget(self.timer_label)

        layout.addSpacing(20)

        # ── Control buttons row ──
        controls_frame = QFrame()
        controls_frame.setObjectName("callControls")
        ctrl_layout = QGridLayout(controls_frame)
        ctrl_layout.setSpacing(16)
        ctrl_layout.setContentsMargins(10, 10, 10, 10)

        self.btn_mute = self._make_ctrl_btn("🔇", "השתק")
        self.btn_speaker = self._make_ctrl_btn("🔊", "רמקול")
        self.btn_hold = self._make_ctrl_btn("⏸", "המתנה")
        self.btn_dtmf = self._make_ctrl_btn("🔢", "מקשים")
        self.btn_add = self._make_ctrl_btn("➕", "הוסף שיחה")
        self.btn_record = self._make_ctrl_btn("⏺", "הקלטה")

        ctrl_layout.addWidget(self.btn_mute, 0, 2)
        ctrl_layout.addWidget(self.btn_speaker, 0, 1)
        ctrl_layout.addWidget(self.btn_hold, 0, 0)
        ctrl_layout.addWidget(self.btn_dtmf, 1, 2)
        ctrl_layout.addWidget(self.btn_add, 1, 1)
        ctrl_layout.addWidget(self.btn_record, 1, 0)

        layout.addWidget(controls_frame)

        # ── DTMF pad (hidden by default) ──
        self.dtmf_frame = QFrame()
        self.dtmf_frame.setObjectName("dtmfPad")
        self.dtmf_frame.setVisible(False)
        dtmf_layout = QGridLayout(self.dtmf_frame)
        dtmf_layout.setSpacing(8)
        dtmf_digits = [
            "1","2","3","4","5","6","7","8","9","*","0","#"
        ]
        for i, d in enumerate(dtmf_digits):
            row, col = divmod(i, 3)
            col = 2 - col
            b = QPushButton(d)
            b.setObjectName("dtmfButton")
            b.setMinimumHeight(48)
            b.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, t=d: self.bt.send_dtmf(t))
            dtmf_layout.addWidget(b, row, col)
        layout.addWidget(self.dtmf_frame)

        layout.addStretch()

        # ── Hangup button ──
        hangup_container = QWidget()
        hangup_layout = QHBoxLayout(hangup_container)
        hangup_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_hangup = QPushButton("📵")
        self.btn_hangup.setObjectName("hangupButton")
        self.btn_hangup.setFixedSize(80, 80)
        self.btn_hangup.setFont(QFont("Segoe UI Emoji", 30))
        self.btn_hangup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hangup.clicked.connect(self.hangup_requested)
        hangup_layout.addWidget(self.btn_hangup)

        layout.addWidget(hangup_container)
        layout.addSpacing(10)

        # Connect controls
        self.btn_mute.clicked.connect(self._toggle_mute)
        self.btn_speaker.clicked.connect(self._toggle_speaker)
        self.btn_hold.clicked.connect(self._toggle_hold)
        self.btn_dtmf.clicked.connect(self._toggle_dtmf)

        self._muted = False
        self._speaker = True  # BT = always speaker
        self._on_hold = False

    def _make_ctrl_btn(self, icon: str, label: str) -> QPushButton:
        btn = QPushButton(f"{icon}\n{label}")
        btn.setObjectName("callControlBtn")
        btn.setMinimumSize(90, 70)
        btn.setFont(QFont("Segoe UI", 9))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setCheckable(True)
        return btn

    def start_call(self, call_info: CallInfo):
        name = call_info.name or ""
        number = call_info.number

        if name:
            self.name_label.setText(name)
            self.number_label.setText(number)
        else:
            self.name_label.setText(number)
            self.number_label.setText("")

        if call_info.direction == "incoming":
            self.status_label.setText("שיחה נכנסת")
        else:
            self.status_label.setText("מחייג...")

        self.timer_label.setText("00:00")
        self._active = False

        if call_info.status == "active":
            self._activate(call_info)

    def _activate(self, call_info: CallInfo = None):
        self._active = True
        self.status_label.setText("🔗 שיחה פעילה")
        self._start_time = (call_info.start_time
                            if call_info else time.time())
        self._timer.start(1000)

    def end_call(self):
        self._active = False
        self._timer.stop()
        self.status_label.setText("השיחה הסתיימה")

    def _tick(self):
        if not self._active:
            return
        elapsed = int(time.time() - self._start_time)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        if h:
            self.timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")
        else:
            self.timer_label.setText(f"{m:02d}:{s:02d}")

    def _toggle_mute(self):
        self._muted = not self._muted
        self.btn_mute.setChecked(self._muted)
        if self._muted:
            self.btn_mute.setText("🎙\nהשתק פעיל")
            self.bt.set_mic_volume(0)
        else:
            self.btn_mute.setText("🔇\nהשתק")
            self.bt.set_mic_volume(10)

    def _toggle_speaker(self):
        pass  # BT audio is already routed to computer

    def _toggle_hold(self):
        self._on_hold = not self._on_hold
        self.btn_hold.setChecked(self._on_hold)
        if self._on_hold:
            self.bt._send_at("AT+CHLD=2")
            self.status_label.setText("⏸ שיחה בהמתנה")
        else:
            self.bt._send_at("AT+CHLD=2")
            self.status_label.setText("🔗 שיחה פעילה")

    def _toggle_dtmf(self):
        self._show_dtmf = not self._show_dtmf
        self.dtmf_frame.setVisible(self._show_dtmf)
        self.btn_dtmf.setChecked(self._show_dtmf)
