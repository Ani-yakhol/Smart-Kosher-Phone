#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SendButton — כפתור שליחה עגול מודרני: חץ ^ בתוך עיגול שקוף"""

from PyQt6.QtWidgets import QAbstractButton, QSizePolicy
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath


class SendButton(QAbstractButton):
    """
    כפתור שליחה בסגנון מודרני — עיגול שקוף עם מסגרת דקה,
    ובתוכו חץ ^ (chevron). מסתובב אוטומטית לפי כיוון RTL/LTR
    (מצביע קדימה — ימינה בעברית, שמאלה באנגלית) כדי להתאים
    לתחושת "שליחה" הטבעית בכל שפה.
    """

    def __init__(self, parent=None, diameter: int = 52, point_up: bool = True):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self._point_up = point_up

        # Colors — overridable to match theme
        self.ring_color = QColor("#1976D2")
        self.chevron_color = QColor("#1976D2")
        self.hover_fill = QColor(25, 118, 210, 28)
        self.disabled_color = QColor("#B0B4BA")

    def sizeHint(self):
        return self.size()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(2, 2, self._diameter - 4, self._diameter - 4)
        ring = self.disabled_color if not self.isEnabled() else self.ring_color
        chevron = self.disabled_color if not self.isEnabled() else self.chevron_color

        # Transparent circle, subtle hover fill
        if self.isEnabled() and self.underMouse():
            p.setBrush(self.hover_fill)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(ring, 1.6)
        p.setPen(pen)
        p.drawEllipse(rect)

        # Chevron (^) centered, pointing up by default
        cx, cy = rect.center().x(), rect.center().y()
        w = rect.width() * 0.30
        h = rect.height() * 0.22

        path = QPainterPath()
        if self._point_up:
            path.moveTo(cx - w, cy + h * 0.6)
            path.lineTo(cx, cy - h * 0.6)
            path.lineTo(cx + w, cy + h * 0.6)
        else:
            path.moveTo(cx - w, cy - h * 0.6)
            path.lineTo(cx, cy + h * 0.6)
            path.lineTo(cx + w, cy - h * 0.6)

        chevron_pen = QPen(chevron, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(chevron_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        p.end()
