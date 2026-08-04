#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SideNav v1.0 — סרגל ניווט עם אייקון האפליקציה"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtGui import QFont, QPixmap

ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "resources", "icon_256.png")


def _load_icon(size: int = 36) -> QPixmap:
    """Load the app's designed icon and scale it smoothly for the nav header."""
    pixmap = QPixmap(ICON_PATH)
    if pixmap.isNull():
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        return pixmap
    return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)


class SideNavButton(QPushButton):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("sideNavBtn")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(44)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setText(label)
        self.setFont(QFont("Segoe UI", 10))

        self._badge = QLabel("", self)
        self._badge.setObjectName("sideNavBadge")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self._badge.setFixedSize(16, 16)
        self._badge.setVisible(False)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._badge.move(4, 4)

    def set_badge(self, text: str):
        self._badge.setText(text)
        self._badge.setVisible(bool(text))


class SideNav(QWidget):
    page_changed = Signal(int)

    def __init__(self, app_name="פלאפון כשר חכם", version="v1.0", parent=None):
        super().__init__(parent)
        self.setObjectName("sideNav")
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setFixedWidth(152)
        self._buttons: list[SideNavButton] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Logo header ──
        logo_frame = QFrame()
        logo_frame.setObjectName("sideNavLogo")
        logo_frame.setFixedHeight(72)
        logo_ly = QHBoxLayout(logo_frame)
        logo_ly.setContentsMargins(10, 8, 10, 8)
        logo_ly.setSpacing(8)

        # App icon
        self.logo_icon = QLabel()
        self.logo_icon.setFixedSize(36, 36)
        self.logo_icon.setPixmap(_load_icon(36))
        self.logo_icon.setScaledContents(True)
        logo_ly.addWidget(self.logo_icon)

        name_col = QVBoxLayout()
        name_col.setSpacing(1)
        self.app_name_lbl = QLabel(app_name)
        self.app_name_lbl.setObjectName("sideNavAppName")
        self.app_name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.app_name_lbl.setWordWrap(True)
        name_col.addWidget(self.app_name_lbl)
        self.ver_lbl = QLabel(version)
        self.ver_lbl.setObjectName("sideNavVersion")
        self.ver_lbl.setFont(QFont("Segoe UI", 7))
        name_col.addWidget(self.ver_lbl)
        logo_ly.addLayout(name_col, 1)

        outer.addWidget(logo_frame)

        d1 = QFrame(); d1.setObjectName("sideNavDivider")
        d1.setFrameShape(QFrame.Shape.HLine); d1.setFixedHeight(1)
        outer.addWidget(d1)

        self._btn_area = QWidget(); self._btn_area.setObjectName("sideNavBtnArea")
        self._btn_ly = QVBoxLayout(self._btn_area)
        self._btn_ly.setContentsMargins(4, 4, 4, 4)
        self._btn_ly.setSpacing(1)
        outer.addWidget(self._btn_area, 1)

        d2 = QFrame(); d2.setObjectName("sideNavDivider")
        d2.setFrameShape(QFrame.Shape.HLine); d2.setFixedHeight(1)
        outer.addWidget(d2)

        footer = QLabel(version)
        footer.setObjectName("sideNavFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFont(QFont("Segoe UI", 7))
        footer.setFixedHeight(18)
        outer.addWidget(footer)

    def set_app_name(self, name: str):
        self.app_name_lbl.setText(name)

    def add_nav_item(self, label: str, badge: str = "") -> SideNavButton:
        btn = SideNavButton(label)
        if badge:
            btn.set_badge(badge)
        idx = len(self._buttons)
        btn.clicked.connect(lambda _c, i=idx: self._on_clicked(i))
        self._btn_ly.addWidget(btn)
        self._buttons.append(btn)
        return btn

    def add_spacer(self):
        self._btn_ly.addStretch()

    def _on_clicked(self, idx: int):
        self.set_active(idx)
        self.page_changed.emit(idx)

    def set_active(self, idx: int):
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == idx)

    def set_badge(self, idx: int, text: str):
        if 0 <= idx < len(self._buttons):
            self._buttons[idx].set_badge(text)
