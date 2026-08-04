#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""דף placeholder לתכונות עתידיות — עם תמיכה בשפה"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from app.core.language_manager import Translatable


class StubPage(QWidget, Translatable):
    def __init__(self, language_manager, name_he: str, name_en: str,
                 desc_he: str = "", desc_en: str = "", parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.setObjectName("stubPage")
        self.setLayoutDirection(language_manager.direction)

        ly = QVBoxLayout(self)
        ly.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.setSpacing(20)

        icon = QLabel("🚧")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont("Segoe UI Emoji", 64))
        ly.addWidget(icon)

        title = QLabel()
        title.setObjectName("stubTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.tr_set(title, name_he, name_en)
        ly.addWidget(title)

        badge = QLabel()
        badge.setObjectName("stubBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFont(QFont("Segoe UI", 13))
        self.tr_set(badge, "כרגע בפיתוח — יהיה זמין בקרוב",
                    "Currently in development — coming soon")
        ly.addWidget(badge)

        if desc_he or desc_en:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setObjectName("stubSep")
            ly.addWidget(sep)

            desc = QLabel()
            desc.setObjectName("stubDesc")
            desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc.setFont(QFont("Segoe UI", 11))
            desc.setWordWrap(True)
            desc.setMaximumWidth(500)
            self.tr_set(desc, desc_he, desc_en)
            ly.addWidget(desc)

        language_manager.language_applied.connect(
            lambda _l: (self.setLayoutDirection(language_manager.direction),
                        self.retranslate()))
