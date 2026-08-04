#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LanguageManager — ניהול שפה בזמן אמת
מחיל RTL/LTR על כל חלונות האפליקציה מיידית ללא הפעלה מחדש
"""

import json
import os
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QObject, pyqtSignal as Signal

SETTINGS_PATH = os.path.join(
    os.path.expanduser("~"), "BluePhone", "settings.json")


def _load() -> dict:
    try:
        if os.path.exists(SETTINGS_PATH):
            return json.loads(open(SETTINGS_PATH, encoding="utf-8").read())
    except Exception:
        pass
    return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    open(SETTINGS_PATH, "w", encoding="utf-8").write(
        json.dumps(data, ensure_ascii=False, indent=2))


APP_NAMES = {
    "he": "פלאפון כשר חכם",
    "en": "Smart Kosher Phone",
}

NAV_LABELS_HE = [
    "ממשק שיחה", "מכשירים", "תא קולי", "בייביסיטר",
    "קו תכנים", "הודעות", "בית חכם", "מחשב שלי",
    "הגדרות", "אודות",
]
NAV_LABELS_EN = [
    "Call Interface", "Devices", "Voicemail", "Baby Monitor",
    "IVR Line", "Messages", "Smart Home", "My Computer",
    "Settings", "About",
]

CALL_TABS_HE = ["חיוג", "שיחה פעילה", "אנשי קשר",
                "יומן שיחות", "הקלטות", "הגדרות שיחה"]
CALL_TABS_EN = ["Dial", "Active Call", "Contacts",
                "Call Log", "Recordings", "Call Settings"]


class LanguageManager(QObject):
    language_applied = Signal(str)   # "he" | "en"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lang = _load().get("language", "he")

    @property
    def lang(self) -> str:
        return self._lang

    @property
    def is_rtl(self) -> bool:
        return self._lang != "en"

    @property
    def direction(self) -> Qt.LayoutDirection:
        return Qt.LayoutDirection.RightToLeft if self.is_rtl else Qt.LayoutDirection.LeftToRight

    @property
    def app_name(self) -> str:
        return APP_NAMES.get(self._lang, APP_NAMES["he"])

    @property
    def nav_labels(self) -> list:
        return NAV_LABELS_HE if self.is_rtl else NAV_LABELS_EN

    @property
    def call_tab_labels(self) -> list:
        return CALL_TABS_HE if self.is_rtl else CALL_TABS_EN

    def apply_language(self, lang: str, main_window=None):
        """
        החל שפה מיידית — עדכן כל ה-widgets בלי הפעלה מחדש
        """
        if lang == self._lang and main_window is None:
            return

        self._lang = lang
        data = _load()
        data["language"] = lang
        _save(data)

        app = QApplication.instance()
        direction = self.direction

        # Apply to QApplication globally
        app.setLayoutDirection(direction)

        # Update window title and app name
        if app:
            name = self.app_name
            app.setApplicationName(name)
            app.setApplicationDisplayName(f"{name} v1.0")

        if main_window:
            self._apply_to_window(main_window, direction)

        self.language_applied.emit(lang)

    def _apply_to_window(self, window, direction: Qt.LayoutDirection):
        """עדכן את כל חלונות ה-widget בזמן אמת"""
        app_name = self.app_name

        # Window title
        window.setWindowTitle(f"{app_name} v1.0")
        window.setLayoutDirection(direction)

        # Side nav
        if hasattr(window, 'side_nav'):
            window.side_nav.setLayoutDirection(direction)
            window.side_nav.set_app_name(app_name)
            labels = self.nav_labels
            for i, btn in enumerate(window.side_nav._buttons):
                if i < len(labels):
                    btn.setText(labels[i])

        # Body direction (must stay LTR for physical layout)
        # page_stack direction
        if hasattr(window, 'page_stack'):
            window.page_stack.setLayoutDirection(direction)

        # Call tabs
        if hasattr(window, 'call_tabs'):
            window.call_tabs.setLayoutDirection(direction)
            labels = self.call_tab_labels
            for i in range(min(window.call_tabs.count(), len(labels))):
                window.call_tabs.setTabText(i, labels[i])

        # call_container
        if hasattr(window, '_call_container'):
            window._call_container.setLayoutDirection(direction)

        # Force repaint
        window.update()

    @staticmethod
    def get_saved_language() -> str:
        return _load().get("language", "he")


class Translatable:
    """
    Mixin for pages/widgets that need full-text live translation.
    Usage:
        class MyPage(QWidget, Translatable):
            def __init__(self, language_manager, ...):
                super().__init__()
                self._init_translator(language_manager)
                lbl = QLabel()
                self.tr_set(lbl, "כותרת", "Title")
                ...
                language_manager.language_applied.connect(lambda _l: self.retranslate())
    """

    def _init_translator(self, language_manager: "LanguageManager"):
        self._lang_mgr = language_manager
        self._tr_items = []

    def t(self, he: str, en: str) -> str:
        """Return text in current language without registering for live update."""
        lm = getattr(self, "_lang_mgr", None)
        return he if (lm is None or lm.is_rtl) else en

    def tr_set(self, widget, he: str, en: str, setter: str = "setText"):
        """Set text now, and remember it so retranslate() can re-apply it later."""
        text = self.t(he, en)
        getattr(widget, setter)(text)
        self._tr_items.append((widget, setter, he, en, None))
        return widget

    def tr_tab(self, tab_widget, index: int, he: str, en: str):
        """Register a QTabWidget tab label for live translation."""
        tab_widget.setTabText(index, self.t(he, en))
        self._tr_items.append((tab_widget, "__tab__", he, en, index))

    def tr_item(self, list_widget, index: int, he: str, en: str):
        """Register a QListWidget/QComboBox item label for live translation."""
        self._tr_items.append((list_widget, "__item__", he, en, index))
        if hasattr(list_widget, "setItemText"):
            list_widget.setItemText(index, self.t(he, en))
        elif hasattr(list_widget, "item"):
            it = list_widget.item(index)
            if it:
                it.setText(self.t(he, en))

    def retranslate(self):
        """Re-apply every registered text according to the current language."""
        for widget, setter, he, en, extra in getattr(self, "_tr_items", []):
            text = self.t(he, en)
            try:
                if setter == "__tab__":
                    widget.setTabText(extra, text)
                elif setter == "__item__":
                    if hasattr(widget, "setItemText"):
                        widget.setItemText(extra, text)
                    elif hasattr(widget, "item"):
                        it = widget.item(extra)
                        if it:
                            it.setText(text)
                else:
                    getattr(widget, setter)(text)
            except RuntimeError:
                pass   # underlying C++ widget already destroyed
        if hasattr(self, "_on_retranslate_extra"):
            self._on_retranslate_extra()
