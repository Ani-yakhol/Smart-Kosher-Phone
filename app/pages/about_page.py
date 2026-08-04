#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""דף אודות v1.0 — עם תמיכה בשפה"""

import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap

from app.core.language_manager import Translatable

ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "resources", "icon_256.png")


class AboutPage(QWidget, Translatable):
    def __init__(self, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.setObjectName("aboutPage")
        self.setLayoutDirection(language_manager.direction)

        ly = QVBoxLayout(self)
        ly.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.setSpacing(14)
        ly.setContentsMargins(40, 30, 40, 30)

        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(112, 112)
        pix = QPixmap(ICON_PATH)
        if not pix.isNull():
            icon.setPixmap(pix.scaled(112, 112, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation))
        icon.setObjectName("aboutIcon")
        ly.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        name = QLabel()
        name.setObjectName("aboutTitle")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.tr_set(name, "פלאפון כשר חכם", "Smart Kosher Phone")
        ly.addWidget(name)

        en_name = QLabel()
        en_name.setObjectName("aboutVersion")
        en_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        en_name.setFont(QFont("Segoe UI", 12))
        self.tr_set(en_name, "Smart Kosher Phone", "פלאפון כשר חכם")
        ly.addWidget(en_name)

        version = QLabel()
        version.setObjectName("aboutVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setFont(QFont("Segoe UI", 13))
        self.tr_set(version, "גרסה 1.0", "Version 1.0")
        ly.addWidget(version)

        tagline = QLabel()
        tagline.setObjectName("aboutTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setFont(QFont("Segoe UI", 11))
        self.tr_set(tagline, "דיבורית בלוטוס מתקדמת למחשב Windows",
                    "Advanced Bluetooth hands-free for Windows PC")
        ly.addWidget(tagline)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("aboutSep"); ly.addWidget(sep)

        tech = QLabel(
            "Python 3.10+  •  PyQt6 (Qt6)  •  Bleak\n"
            "socket.AF_BLUETOOTH / RFCOMM / HFP 1.6  •  AT Commands\n"
            "Vosk  •  DTMF TextModem\n"
            "sounddevice  •  Windows BT Stack (WinRT)"
        )
        tech.setObjectName("aboutTech")
        tech.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tech.setWordWrap(True)
        self.tr_set(tech,
            "Python 3.10+  •  PyQt6 (Qt6)  •  Bleak\n"
            "socket.AF_BLUETOOTH / RFCOMM / HFP 1.6  •  פקודות AT\n"
            "Vosk (זיהוי קול אופליין)  •  DTMF TextModem\n"
            "sounddevice  •  Windows BT Stack (WinRT)",
            "Python 3.10+  •  PyQt6 (Qt6)  •  Bleak\n"
            "socket.AF_BLUETOOTH / RFCOMM / HFP 1.6  •  AT Commands\n"
            "Vosk (offline speech recognition)  •  DTMF TextModem\n"
            "sounddevice  •  Windows BT Stack (WinRT)")
        ly.addWidget(tech)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setObjectName("aboutSep"); ly.addWidget(sep2)

        credits_title = QLabel()
        credits_title.setObjectName("creditsTitle")
        credits_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.tr_set(credits_title, "קרדיטים", "Credits")
        ly.addWidget(credits_title)

        credits = QLabel()
        credits.setObjectName("aboutCredits")
        credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits.setWordWrap(True)
        self.tr_set(credits,
            "פיתוח וארכיטקטורה: Smart Kosher Phone Project\n\n"
            "ספריות קוד פתוח:\n"
            "PyQt6 — Qt for Python  ©  The Qt Company  (LGPL v3)\n"
            "Bleak — Bluetooth LE Client  ©  Henrik Blidh  (MIT)\n"
            "Vosk — זיהוי דיבור אופליין  ©  Alpha Cephei  (Apache 2.0)\n"
            "SpeechRecognition  ©  Anthony Zhang  (BSD)\n"
            "sounddevice  ©  Matthias Geier  (MIT)\n"
            "Python  ©  Python Software Foundation  (PSF)",
            "Development and architecture: Smart Kosher Phone Project\n\n"
            "Open-source libraries:\n"
            "PyQt6 — Qt for Python  ©  The Qt Company  (LGPL v3)\n"
            "Bleak — Bluetooth LE Client  ©  Henrik Blidh  (MIT)\n"
            "Vosk — Offline Speech Recognition  ©  Alpha Cephei  (Apache 2.0)\n"
            "SpeechRecognition  ©  Anthony Zhang  (BSD)\n"
            "sounddevice  ©  Matthias Geier  (MIT)\n"
            "Python  ©  Python Software Foundation  (PSF)")
        ly.addWidget(credits)

        sep3 = QFrame(); sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setObjectName("aboutSep"); ly.addWidget(sep3)

        footer = QLabel()
        footer.setObjectName("aboutFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFont(QFont("Segoe UI", 9))
        self.tr_set(footer, "גרסה 1.0  •  © 2024  •  כל הזכויות שמורות  •  רישיון MIT",
                    "Version 1.0  •  © 2024  •  All rights reserved  •  MIT License")
        ly.addWidget(footer)

        language_manager.language_applied.connect(
            lambda _l: (self.setLayoutDirection(language_manager.direction),
                        self.retranslate()))
