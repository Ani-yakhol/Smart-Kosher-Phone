#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ServiceToggles — ניהול מצב הפעלה/כיבוי לכל לשונית בנפרד
מאפשר לכבות זמנית שירות מסוים (למשל 'בית חכם') מבלי לאבד הגדרות.
המצב נשמר ל-settings.json ונטען מחדש בכל הפעלה.
"""

import json
import os
from PyQt6.QtCore import QObject, pyqtSignal as Signal

SETTINGS_PATH = os.path.join(
    os.path.expanduser("~"), "BluePhone", "settings.json")

# Pages that get an on/off switch at the top.
# 'devices', 'settings' and 'about' are intentionally excluded.
TOGGLABLE_PAGES = [
    "call", "voicemail", "babysitter", "ivr",
    "messaging", "smarthome", "mypc",
]


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


class ServiceToggles(QObject):
    """מחזיק מצב הפעלה/כיבוי לכל לשונית, עם שמירה אוטומטית"""

    toggle_changed = Signal(str, bool)   # page_id, enabled

    def __init__(self, parent=None):
        super().__init__(parent)
        data = _load()
        saved = data.get("service_toggles", {})
        self._state = {pid: bool(saved.get(pid, True)) for pid in TOGGLABLE_PAGES}

    def is_enabled(self, page_id: str) -> bool:
        return self._state.get(page_id, True)

    def set_enabled(self, page_id: str, enabled: bool):
        if self._state.get(page_id) == enabled:
            return
        self._state[page_id] = enabled
        data = _load()
        data.setdefault("service_toggles", {})[page_id] = enabled
        _save(data)
        self.toggle_changed.emit(page_id, enabled)
