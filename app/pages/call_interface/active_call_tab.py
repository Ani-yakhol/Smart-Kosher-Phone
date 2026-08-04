#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
לשונית שיחה פעילה — כולל תצוגת שיחה נכנסת בתוך הלשונית עצמה
"""

import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer
from PyQt6.QtGui import QFont
from app.bluetooth_manager import CallInfo
from app.core.language_manager import Translatable


# ══════════════════════════════════════════════
#  Idle state widget
# ══════════════════════════════════════════════
class IdleWidget(QWidget, Translatable):
    def __init__(self, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        ly = QVBoxLayout(self)
        ly.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.setSpacing(16)
        icon = QLabel("📵")
        icon.setFont(QFont("Segoe UI Emoji", 56))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(icon)
        lbl = QLabel()
        lbl.setObjectName("idleLabel")
        lbl.setFont(QFont("Segoe UI", 14))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tr_set(lbl, "אין שיחה פעילה", "No active call")
        ly.addWidget(lbl)
        hint = QLabel()
        hint.setObjectName("hintLabel")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setFont(QFont("Segoe UI", 10))
        self.tr_set(hint, "חייג מלשונית החיוג או המתן לשיחה נכנסת",
                    "Dial from the Dial tab or wait for an incoming call")
        ly.addWidget(hint)


# ══════════════════════════════════════════════
#  Incoming call widget (shown inside tab)
# ══════════════════════════════════════════════
class IncomingWidget(QWidget, Translatable):
    answered  = Signal()
    rejected  = Signal()
    vm_signal = Signal()   # שלח לתא קולי

    def __init__(self, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.setObjectName("incomingWidget")
        self.setLayoutDirection(language_manager.direction)
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_state = False
        self._build()
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self.retranslate()

    def _build(self):
        ly = QVBoxLayout(self)
        ly.setContentsMargins(40, 40, 40, 40)
        ly.setSpacing(0)
        ly.setAlignment(Qt.AlignmentFlag.AlignCenter)

        incoming_lbl = QLabel()
        incoming_lbl.setObjectName("incomingLabel")
        incoming_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        incoming_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.tr_set(incoming_lbl, "📲  שיחה נכנסת", "📲  Incoming Call")
        ly.addWidget(incoming_lbl)
        ly.addSpacing(20)

        self.avatar = QLabel("👤")
        self.avatar.setObjectName("incomingAvatar")
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setFont(QFont("Segoe UI Emoji", 72))
        ly.addWidget(self.avatar)
        ly.addSpacing(16)

        self.name_lbl = QLabel("")
        self.name_lbl.setObjectName("incomingName")
        self.name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_lbl.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self.name_lbl.setWordWrap(True)
        ly.addWidget(self.name_lbl)

        self.number_lbl = QLabel("")
        self.number_lbl.setObjectName("incomingNumber")
        self.number_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_lbl.setFont(QFont("Segoe UI", 15))
        self.number_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        ly.addWidget(self.number_lbl)
        ly.addSpacing(10)

        self.ring_lbl = QLabel("〜  〜  〜")
        self.ring_lbl.setObjectName("ringLabel")
        self.ring_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ring_lbl.setFont(QFont("Segoe UI", 20))
        ly.addWidget(self.ring_lbl)
        ly.addSpacing(30)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(30)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_reject = QPushButton("📵")
        self.btn_reject.setObjectName("rejectButton")
        self.btn_reject.setFixedSize(86, 86)
        self.btn_reject.setFont(QFont("Segoe UI Emoji", 34))
        self.btn_reject.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tr_set(self.btn_reject, "דחה שיחה", "Decline call", setter="setToolTip")
        self.btn_reject.clicked.connect(self._on_reject)

        self.btn_vm = QPushButton("📬")
        self.btn_vm.setObjectName("vmRouteButton")
        self.btn_vm.setFixedSize(62, 62)
        self.btn_vm.setFont(QFont("Segoe UI Emoji", 24))
        self.btn_vm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tr_set(self.btn_vm, "שלח לתא קולי", "Send to voicemail", setter="setToolTip")
        self.btn_vm.clicked.connect(self._on_vm)

        self.btn_answer = QPushButton("📞")
        self.btn_answer.setObjectName("answerButton")
        self.btn_answer.setFixedSize(86, 86)
        self.btn_answer.setFont(QFont("Segoe UI Emoji", 34))
        self.btn_answer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tr_set(self.btn_answer, "ענה לשיחה", "Answer call", setter="setToolTip")
        self.btn_answer.clicked.connect(self._on_answer)

        btn_row.addWidget(self.btn_reject)
        btn_row.addWidget(self.btn_vm)
        btn_row.addWidget(self.btn_answer)
        ly.addLayout(btn_row)
        ly.addSpacing(8)

        lbl_row = QHBoxLayout()
        lbl_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_row.setSpacing(30)
        for he, en in [("דחה", "Decline"), ("תא קולי", "Voicemail"), ("ענה", "Answer")]:
            l = QLabel(); l.setObjectName("btnLabel")
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setFont(QFont("Segoe UI", 10))
            self.tr_set(l, he, en)
            lbl_row.addWidget(l)
        ly.addLayout(lbl_row)
        ly.addStretch()

    def show_incoming(self, call_info: CallInfo):
        name = call_info.name or ""
        number = call_info.number
        self.name_lbl.setText(name if name else number)
        self.number_lbl.setText(number if name else "")
        self.number_lbl.setVisible(bool(name))
        self._pulse_timer.start(650)

    def hide_incoming(self):
        self._pulse_timer.stop()

    def _pulse(self):
        self._pulse_state = not self._pulse_state
        self.ring_lbl.setText("〜  〜  〜" if self._pulse_state else "  〜  〜  ")

    def _on_answer(self):
        self.hide_incoming(); self.answered.emit()

    def _on_reject(self):
        self.hide_incoming(); self.rejected.emit()

    def _on_vm(self):
        self.hide_incoming(); self.vm_signal.emit()


# ══════════════════════════════════════════════
#  Active call controls widget
# ══════════════════════════════════════════════
class ActiveWidget(QWidget, Translatable):
    hangup_requested = Signal()

    def __init__(self, bt_manager, language_manager, rec_manager=None, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.bt  = bt_manager
        self.rec = rec_manager
        self._start_time = 0
        self._active = False
        self._muted = False
        self._on_hold = False
        self._show_dtmf = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._build()
        language_manager.language_applied.connect(lambda _l: self.retranslate())

    def _build(self):
        ly = QVBoxLayout(self)
        ly.setContentsMargins(30, 24, 30, 16)
        ly.setSpacing(0)

        # Avatar
        self.avatar = QLabel("👤")
        self.avatar.setObjectName("callAvatar")
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setFont(QFont("Segoe UI Emoji", 52))
        self.avatar.setFixedHeight(96)
        ly.addWidget(self.avatar)
        ly.addSpacing(8)

        self.name_lbl = QLabel("—")
        self.name_lbl.setObjectName("callName")
        self.name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_lbl.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        ly.addWidget(self.name_lbl)

        self.number_lbl = QLabel("")
        self.number_lbl.setObjectName("callNumber")
        self.number_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_lbl.setFont(QFont("Segoe UI", 13))
        self.number_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        ly.addWidget(self.number_lbl)
        ly.addSpacing(6)

        self.status_lbl = QLabel()
        self.status_lbl.setObjectName("callStatus")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tr_set(self.status_lbl, "ממתין…", "Waiting…")
        ly.addWidget(self.status_lbl)

        self.timer_lbl = QLabel("00:00")
        self.timer_lbl.setObjectName("callTimer")
        self.timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_lbl.setFont(QFont("Courier New", 34, QFont.Weight.Bold))
        ly.addWidget(self.timer_lbl)

        self.rec_lbl = QLabel("")
        self.rec_lbl.setObjectName("recIndicator")
        self.rec_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(self.rec_lbl)
        ly.addSpacing(10)

        # Controls
        ctrl = QFrame(); ctrl.setObjectName("callControls")
        cg = QGridLayout(ctrl); cg.setSpacing(12)
        cg.setContentsMargins(10, 10, 10, 10)

        def mk(icon, he, en):
            b = QPushButton()
            b.setObjectName("callControlBtn")
            b.setMinimumSize(96, 68); b.setFont(QFont("Segoe UI", 9))
            b.setCursor(Qt.CursorShape.PointingHandCursor); b.setCheckable(True)
            self.tr_set(b, f"{icon}\n{he}", f"{icon}\n{en}")
            return b

        self.btn_mute   = mk("🔇", "השתק", "Mute")
        self.btn_hold   = mk("⏸",  "המתנה", "Hold")
        self.btn_dtmf   = mk("🔢", "מקשים", "Keypad")
        self.btn_rec    = mk("⏺",  "הקלטה", "Record")
        self.btn_redial = mk("🔄", "חייג שוב", "Redial")
        self.btn_xfer   = mk("🔀", "העבר שמע", "Transfer Audio")

        cg.addWidget(self.btn_mute,   0, 2)
        cg.addWidget(self.btn_hold,   0, 1)
        cg.addWidget(self.btn_dtmf,   0, 0)
        cg.addWidget(self.btn_rec,    1, 2)
        cg.addWidget(self.btn_redial, 1, 1)
        cg.addWidget(self.btn_xfer,   1, 0)
        ly.addWidget(ctrl)

        # DTMF
        self.dtmf_frame = QFrame(); self.dtmf_frame.setObjectName("dtmfPad")
        self.dtmf_frame.setVisible(False)
        dg = QGridLayout(self.dtmf_frame); dg.setSpacing(8)
        for i, d in enumerate("123456789*0#"):
            r, c = divmod(i, 3); c = 2-c
            b = QPushButton(d); b.setObjectName("dtmfButton")
            b.setMinimumHeight(44); b.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, t=d: self.bt.send_dtmf(t))
            dg.addWidget(b, r, c)
        ly.addWidget(self.dtmf_frame)
        ly.addStretch()

        # Hangup
        hrow = QHBoxLayout(); hrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_hangup = QPushButton("📵")
        self.btn_hangup.setObjectName("hangupButton")
        self.btn_hangup.setFixedSize(82, 82)
        self.btn_hangup.setFont(QFont("Segoe UI Emoji", 30))
        self.btn_hangup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hangup.clicked.connect(self.hangup_requested)
        hrow.addWidget(self.btn_hangup)
        ly.addLayout(hrow); ly.addSpacing(8)

        self.btn_mute.clicked.connect(self._toggle_mute)
        self.btn_hold.clicked.connect(self._toggle_hold)
        self.btn_dtmf.clicked.connect(self._toggle_dtmf)
        self.btn_rec.clicked.connect(self._toggle_rec)
        self.btn_redial.clicked.connect(self.bt.redial)
        self.btn_xfer.clicked.connect(self.bt.connect_audio)

    def start_call(self, info: CallInfo):
        name = info.name or ""
        num  = info.number
        self.name_lbl.setText(name if name else num)
        self.number_lbl.setText(num if name else "")
        dir_txt = self.t("שיחה נכנסת", "Incoming call") if info.direction == "incoming" \
            else self.t("מחייג…", "Dialing…")
        self.status_lbl.setText(dir_txt)
        self.timer_lbl.setText("00:00")
        self._active = False
        if info.status == "active":
            self._activate(info)

    def activate(self, info: CallInfo = None):
        self._activate(info)

    def _activate(self, info=None):
        self._active = True
        self.status_lbl.setText(self.t("🔗  שיחה פעילה", "🔗  Call Active"))
        self._start_time = info.start_time if info else time.time()
        self._timer.start(1000)

    def end_call(self):
        self._active = False
        self._timer.stop()
        self.status_lbl.setText(self.t("השיחה הסתיימה", "Call ended"))
        if self.rec and self.rec.is_recording:
            self.rec.stop_recording()
            self.rec_lbl.setText("")

    def _tick(self):
        if not self._active: return
        e = int(time.time() - self._start_time)
        h, m, s = e//3600, (e%3600)//60, e%60
        self.timer_lbl.setText(
            f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}")

    def _toggle_mute(self):
        self._muted = not self._muted
        self.btn_mute.setChecked(self._muted)
        self.bt.set_mic_volume(0 if self._muted else 10)
        self.btn_mute.setText(self.t("🎙️\nהשתק פעיל", "🎙️\nMuted") if self._muted
                               else self.t("🔇\nהשתק", "🔇\nMute"))

    def _toggle_hold(self):
        self._on_hold = not self._on_hold
        self.btn_hold.setChecked(self._on_hold)
        self.bt.hold_call()
        self.status_lbl.setText(self.t("⏸  המתנה", "⏸  On Hold") if self._on_hold
                                 else self.t("🔗  שיחה פעילה", "🔗  Call Active"))

    def _toggle_dtmf(self):
        self._show_dtmf = not self._show_dtmf
        self.dtmf_frame.setVisible(self._show_dtmf)
        self.btn_dtmf.setChecked(self._show_dtmf)

    def _toggle_rec(self):
        if not self.rec: return
        if self.rec.is_recording:
            self.rec.stop_recording()
            self.btn_rec.setChecked(False)
            self.rec_lbl.setText("")
        else:
            ci = self.bt.current_call
            if ci:
                self.rec.start_recording(ci.number, ci.name, ci.direction)
                self.btn_rec.setChecked(True)
                self.rec_lbl.setText(self.t("⏺  מקליט…", "⏺  Recording…"))


# ══════════════════════════════════════════════
#  ActiveCallTab — main tab widget
# ══════════════════════════════════════════════
class ActiveCallTab(QWidget, Translatable):
    hangup_requested = Signal()
    answer_requested = Signal()
    reject_requested = Signal()
    vm_requested     = Signal()

    # STATE constants
    STATE_IDLE     = 0
    STATE_INCOMING = 1
    STATE_ACTIVE   = 2

    def __init__(self, bt_manager, language_manager, rec_manager=None, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.bt  = bt_manager
        self.rec = rec_manager
        self.setObjectName("callPage")
        self.setLayoutDirection(language_manager.direction)
        self._state = self.STATE_IDLE
        self._build(language_manager)
        language_manager.language_applied.connect(
            lambda _l: self.setLayoutDirection(language_manager.direction))

    def _build(self, language_manager):
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        ly.addWidget(self._stack)

        self._idle_w    = IdleWidget(language_manager)
        self._incoming_w = IncomingWidget(language_manager)
        self._active_w  = ActiveWidget(self.bt, language_manager, self.rec)

        self._stack.addWidget(self._idle_w)      # 0
        self._stack.addWidget(self._incoming_w)  # 1
        self._stack.addWidget(self._active_w)    # 2

        # Wire internal signals
        self._incoming_w.answered.connect(self._on_answered_internally)
        self._incoming_w.rejected.connect(self._on_rejected_internally)
        self._incoming_w.vm_signal.connect(self.vm_requested)
        self._active_w.hangup_requested.connect(self.hangup_requested)

    # ── Public API ────────────────────────────────────────

    def show_idle(self):
        self._state = self.STATE_IDLE
        self._stack.setCurrentIndex(0)

    def show_incoming(self, call_info: CallInfo):
        self._state = self.STATE_INCOMING
        self._incoming_w.show_incoming(call_info)
        self._stack.setCurrentIndex(1)

    def start_call(self, call_info: CallInfo):
        """חיוג יוצא — מציג מסך שיחה פעילה"""
        self._state = self.STATE_ACTIVE
        self._active_w.start_call(call_info)
        self._stack.setCurrentIndex(2)

    def activate_call(self, call_info: CallInfo):
        """שיחה נענתה"""
        self._state = self.STATE_ACTIVE
        self._incoming_w.hide_incoming()
        self._active_w.start_call(call_info)
        self._active_w.activate(call_info)
        self._stack.setCurrentIndex(2)

    def end_call(self):
        self._active_w.end_call()
        QTimer.singleShot(1600, self.show_idle)

    def _on_answered_internally(self):
        self.answer_requested.emit()

    def _on_rejected_internally(self):
        self.reject_requested.emit()
