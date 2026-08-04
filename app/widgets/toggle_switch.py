#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ToggleSwitch — מתג הפעלה/כיבוי מודרני (iOS-style) עם אנימציה"""

from PyQt6.QtWidgets import QAbstractButton, QSizePolicy
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty as Property, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen


class ToggleSwitch(QAbstractButton):
    """מתג הפעלה/כיבוי עגול חלק, בסגנון iOS/Android מודרני"""

    def __init__(self, parent=None, checked: bool = True):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(46, 26)

        self._knob_pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob_pos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.toggled.connect(self._animate)

        # Colors — overridable per theme
        self.color_on = QColor("#2FA84F")
        self.color_off = QColor("#B0B4BA")
        self.color_knob = QColor("#FFFFFF")

    def _animate(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._knob_pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def get_knob_pos(self):
        return self._knob_pos

    def set_knob_pos(self, value):
        self._knob_pos = value
        self.update()

    knob_pos = Property(float, get_knob_pos, set_knob_pos)

    def sizeHint(self):
        return self.size()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_color = QColor(self.color_off)
        r, g, b = self.color_off.getRgb()[:3]
        r2, g2, b2 = self.color_on.getRgb()[:3]
        t = self._knob_pos
        track_color = QColor(
            int(r + (r2 - r) * t),
            int(g + (g2 - g) * t),
            int(b + (b2 - b) * t),
        )

        track_rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(track_rect, track_rect.height() / 2, track_rect.height() / 2)

        knob_d = self.height() - 6
        travel = self.width() - knob_d - 6
        knob_x = 3 + travel * self._knob_pos
        p.setBrush(self.color_knob)
        p.drawEllipse(QRectF(knob_x, 3, knob_d, knob_d))

        if not self.isEnabled():
            p.setBrush(QColor(255, 255, 255, 90))
            p.drawRoundedRect(track_rect, track_rect.height() / 2, track_rect.height() / 2)

        p.end()
