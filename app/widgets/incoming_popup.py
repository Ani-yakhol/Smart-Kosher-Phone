#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IncomingCallPopup — חלונית קופצת לשיחה נכנסת
מוצגת מעל כל חלונות כשהתוכנה רצה ברקע
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QScreen
from PyQt6.QtWidgets import QApplication

from app.bluetooth_manager import CallInfo
from app.core.language_manager import Translatable


class IncomingCallPopup(QDialog, Translatable):
    """
    חלונית שיחה נכנסת — מופיעה מעל כל שאר החלונות.
    כוללת: שם/מספר מתקשר, מענה, דחייה, השתקה, העברה לתא קולי.
    """
    answered        = Signal()
    rejected        = Signal()
    silenced        = Signal()   # השתק צלצול
    sent_to_vm      = Signal()   # שלח לתא קולי

    def __init__(self, language_manager, parent=None):
        super().__init__(parent,
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.Tool)
        self._init_translator(language_manager)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(self.t("שיחה נכנסת", "Incoming Call"))
        self.setLayoutDirection(language_manager.direction)
        self.setMinimumWidth(360)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_state = False
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._on_no_answer)

        self._build()
        self._position_popup()

        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self.setWindowTitle(self.t("שיחה נכנסת", "Incoming Call"))
        self.retranslate()
        self._position_popup()

    # ── Build ─────────────────────────────────────────────

    def _build(self):
        # Outer container with drop shadow
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        card = QFrame()
        card.setObjectName("popupCard")
        card.setMinimumWidth(340)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        card.setGraphicsEffect(shadow)

        outer.addWidget(card)

        ly = QVBoxLayout(card)
        ly.setContentsMargins(20, 18, 20, 18)
        ly.setSpacing(12)

        # ── Top row: label + dismiss X ──
        top_row = QHBoxLayout()
        self.type_lbl = QLabel()
        self.type_lbl.setObjectName("popupTypeLabel")
        self.type_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.tr_set(self.type_lbl, "📲  שיחה נכנסת", "📲  Incoming Call")
        top_row.addWidget(self.type_lbl)
        top_row.addStretch()

        self.ring_lbl = QLabel("〜")
        self.ring_lbl.setObjectName("popupRingAnim")
        self.ring_lbl.setFont(QFont("Segoe UI", 14))
        top_row.addWidget(self.ring_lbl)
        ly.addLayout(top_row)

        # ── Avatar + caller info ──
        caller_row = QHBoxLayout()
        caller_row.setSpacing(14)

        self.avatar_lbl = QLabel("👤")
        self.avatar_lbl.setObjectName("popupAvatar")
        self.avatar_lbl.setFont(QFont("Segoe UI Emoji", 38))
        self.avatar_lbl.setFixedSize(68, 68)
        self.avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caller_row.addWidget(self.avatar_lbl)

        info_col = QVBoxLayout()
        info_col.setSpacing(4)

        self.name_lbl = QLabel("")
        self.name_lbl.setObjectName("popupName")
        self.name_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.name_lbl.setWordWrap(True)
        info_col.addWidget(self.name_lbl)

        self.number_lbl = QLabel("")
        self.number_lbl.setObjectName("popupNumber")
        self.number_lbl.setFont(QFont("Segoe UI", 12))
        self.number_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        info_col.addWidget(self.number_lbl)

        caller_row.addLayout(info_col, 1)
        ly.addLayout(caller_row)

        # ── Divider ──
        sep = QFrame(); sep.setObjectName("popupSep")
        sep.setFrameShape(QFrame.Shape.HLine); sep.setFixedHeight(1)
        ly.addWidget(sep)

        # ── Action buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        # Answer (green, right side in RTL = first in LTR widget)
        self.btn_answer = self._make_btn("📞", "ענה", "Answer", "#2E7D32", "#43A047", "popupAnswerBtn")
        self.btn_answer.clicked.connect(self._on_answer)

        # Reject (red)
        self.btn_reject = self._make_btn("📵", "דחה", "Decline", "#C62828", "#EF5350", "popupRejectBtn")
        self.btn_reject.clicked.connect(self._on_reject)

        # Silence (grey)
        self.btn_silence = self._make_btn("🔕", "השתק", "Silence", "#455A64", "#607D8B", "popupSilenceBtn")
        self.btn_silence.clicked.connect(self._on_silence)

        # Voicemail (blue)
        self.btn_vm = self._make_btn("📬", "תא קולי", "Voicemail", "#1565C0", "#1976D2", "popupVmBtn")
        self.btn_vm.clicked.connect(self._on_voicemail)

        btn_row.addWidget(self.btn_answer)
        btn_row.addWidget(self.btn_reject)
        btn_row.addWidget(self.btn_silence)
        btn_row.addWidget(self.btn_vm)
        ly.addLayout(btn_row)

        # Labels under buttons
        lbl_row = QHBoxLayout(); lbl_row.setSpacing(10)
        self._btn_labels = []
        for he, en in [("ענה", "Answer"), ("דחה", "Decline"),
                       ("השתק", "Silence"), ("תא קולי", "Voicemail")]:
            lbl = QLabel(); lbl.setObjectName("popupBtnLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); lbl.setFont(QFont("Segoe UI", 8))
            self.tr_set(lbl, he, en)
            lbl_row.addWidget(lbl)
        ly.addLayout(lbl_row)

    def _make_btn(self, icon, tooltip_he, tooltip_en, bg, bg_hover, obj) -> QPushButton:
        btn = QPushButton(icon)
        btn.setObjectName(obj)
        btn.setFixedSize(64, 64)
        btn.setFont(QFont("Segoe UI Emoji", 26))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tr_set(btn, tooltip_he, tooltip_en, setter="setToolTip")
        btn.setStyleSheet(
            f"QPushButton#{obj} {{"
            f"  background:{bg}; border:none; border-radius:32px; color:white;"
            f"}}"
            f"QPushButton#{obj}:hover {{ background:{bg_hover}; }}"
            f"QPushButton#{obj}:pressed {{ background:{bg}; }}"
        )
        return btn

    # ── Positioning ───────────────────────────────────────

    def _position_popup(self):
        """מקם בפינה תחתונה של המסך — ימין ב-RTL, שמאל ב-LTR"""
        screen: QScreen = QApplication.primaryScreen()
        sg = screen.availableGeometry()
        self.adjustSize()
        if self._lang_mgr.is_rtl:
            x = sg.right() - self.width() - 20
        else:
            x = sg.left() + 20
        y = sg.bottom() - self.height() - 40
        self.move(x, y)

    # ── Show/hide ─────────────────────────────────────────

    def show_call(self, call_info: CallInfo):
        name   = call_info.name or ""
        number = call_info.number

        self.name_lbl.setText(name if name else number)
        self.number_lbl.setText(number if name else "")
        self.number_lbl.setVisible(bool(name))

        self._position_popup()
        self.show()
        self.raise_()
        self.activateWindow()
        self._pulse_timer.start(700)
        # Auto-close after 45 s (missed)
        self._auto_close_timer.start(45_000)

    def close_popup(self):
        self._pulse_timer.stop()
        self._auto_close_timer.stop()
        self.hide()

    # ── Pulse animation ───────────────────────────────────

    def _pulse(self):
        self._pulse_state = not self._pulse_state
        self.ring_lbl.setText("〜 〜 〜" if self._pulse_state else " 〜 〜 ")

    # ── Handlers ──────────────────────────────────────────

    def _on_answer(self):
        self.close_popup()
        self.answered.emit()

    def _on_reject(self):
        self.close_popup()
        self.rejected.emit()

    def _on_silence(self):
        self._pulse_timer.stop()
        self.ring_lbl.setText("🔕")
        self.silenced.emit()

    def _on_voicemail(self):
        self.close_popup()
        self.sent_to_vm.emit()

    def _on_no_answer(self):
        self.close_popup()
        # Will be treated as missed in main_window
