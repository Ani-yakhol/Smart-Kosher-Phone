#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TogglablePage — עוטף כל דף עם פס עליון הכולל מתג הפעלה/כיבוי ללשונית.
כאשר המתג כבוי — תוכן הדף מושבת חזותית (אפור) והשירותים הקשורים אליו
(כגון תא קולי אוטומטי / בייביסיטר) מדווחים למנהל ה-toggles ומתעלמים בהתאם.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from app.widgets.toggle_switch import ToggleSwitch
from app.core.language_manager import Translatable


class TogglablePage(QWidget, Translatable):
    """עוטף QWidget של דף עם פס-כותרת שכולל מתג הפעלה/כיבוי"""

    def __init__(self, page_id: str, title_he: str, title_en: str,
                 content: QWidget, service_toggles, language_manager,
                 parent=None):
        super().__init__(parent)
        Translatable._init_translator(self, language_manager)
        self.setObjectName("togglablePage")
        self.page_id = page_id
        self._toggles = service_toggles
        self._content = content

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("pageToggleHeader")
        header.setFixedHeight(42)
        h = QHBoxLayout(header)
        h.setContentsMargins(14, 6, 14, 6)
        h.setSpacing(10)

        self.title_lbl = QLabel()
        self.title_lbl.setObjectName("pageToggleTitle")
        self.title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.tr_set(self.title_lbl, title_he, title_en)
        h.addWidget(self.title_lbl)
        h.addStretch()

        self.status_lbl = QLabel()
        self.status_lbl.setObjectName("pageToggleStatus")
        self.status_lbl.setFont(QFont("Segoe UI", 9))
        h.addWidget(self.status_lbl)

        self.switch = ToggleSwitch(checked=service_toggles.is_enabled(page_id))
        self.switch.setToolTip(self.t(
            "הפעל/כבה שירות זה", "Enable/disable this service"))
        self.switch.toggled.connect(self._on_toggled)
        h.addWidget(self.switch)

        outer.addWidget(header)

        div = QFrame(); div.setObjectName("pageToggleDivider")
        div.setFrameShape(QFrame.Shape.HLine); div.setFixedHeight(1)
        outer.addWidget(div)

        outer.addWidget(content, 1)

        self._update_status_label()
        content.setEnabled(self.switch.isChecked())

        language_manager.language_applied.connect(lambda _l: self.retranslate())

    def _on_toggled(self, checked: bool):
        self._toggles.set_enabled(self.page_id, checked)
        self._content.setEnabled(checked)
        self._update_status_label()

    def _update_status_label(self):
        on = self.switch.isChecked()
        self.status_lbl.setText(self.t("פעיל", "Active") if on
                                 else self.t("כבוי", "Off"))
        self.status_lbl.setStyleSheet(
            "color:#2FA84F;" if on else "color:#B0B4BA;")

    def _on_retranslate_extra(self):
        self._update_status_label()
