#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ThemeManager — ניהול ערכות נושא בהיר/כהה
"""

import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal as Signal


LIGHT_QSS_PATH = os.path.join(os.path.dirname(__file__), "style_light.qss")
DARK_QSS_PATH  = os.path.join(os.path.dirname(__file__), "style_dark.qss")


class ThemeManager(QObject):
    theme_changed = Signal(str)   # "light" | "dark"

    def __init__(self, app: QApplication, parent=None):
        super().__init__(parent)
        self._app = app
        self._current = "light"

    def apply(self, theme: str):
        self._current = theme
        path = LIGHT_QSS_PATH if theme == "light" else DARK_QSS_PATH
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self._app.setStyleSheet(f.read())
        self.theme_changed.emit(theme)

    def toggle(self):
        new = "dark" if self._current == "light" else "light"
        self.apply(new)
        return new

    @property
    def current(self) -> str:
        return self._current

    @property
    def is_dark(self) -> bool:
        return self._current == "dark"
