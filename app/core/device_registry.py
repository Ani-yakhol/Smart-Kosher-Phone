#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeviceRegistry — ניהול רשימת מכשירי בלוטוס מוכרים (מספר מכשירים במקביל).

כל מכשיר מזוהה באופן ייחודי לפי כתובת בלוטוס (MAC address) — זהו המזהה
היחיד שבאמת ייחודי וקבוע לכל מכשיר. בנוסף, כאשר מתאפשר טכנית (הפלאפון
מגיב לפקודת AT+CNUM), המערכת מזהה גם את מספר הטלפון המחובר בפועל לאותו
מכשיר בלוטוס, ושומרת את השיוך device<->number.

מכשיר אחד ניתן לסימון כ"ראשי" (primary) — הוא זה שמשמש כברירת מחדל
לפונקציות השונות בתוכנה (חיוג/מענה) כאשר לא צויין אחרת.

הערה טכנית: מחשב עם מתאם בלוטוס יחיד יכול להחזיק בפועל ערוץ שמע HFP
פעיל אחד בכל רגע נתון (מגבלת מחסנית הבלוטוס של Windows) — כך שגם כאשר
רשומים כמה מכשירים, החיבור הפעיל (עם שמע/שיחות) הוא תמיד מכשיר אחד,
וניתן להחליף בקלות איזה מהם פעיל.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

SETTINGS_PATH = os.path.join(
    os.path.expanduser("~"), "BluePhone", "settings.json")


@dataclass
class KnownDevice:
    address: str
    custom_name: str = ""
    phone_number: str = ""
    is_primary: bool = False
    last_connected: float = 0.0


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


class DeviceRegistry:
    """שומר/טוען את רשימת המכשירים המוכרים מתוך settings.json"""

    def __init__(self):
        self._devices: dict[str, KnownDevice] = {}
        self._load()

    # ── Persistence ─────────────────────────────────────────

    def _load(self):
        data = _load()
        for addr, d in data.get("known_devices", {}).items():
            self._devices[addr] = KnownDevice(
                address=addr,
                custom_name=d.get("custom_name", ""),
                phone_number=d.get("phone_number", ""),
                is_primary=d.get("is_primary", False),
                last_connected=d.get("last_connected", 0.0),
            )

    def _persist(self):
        data = _load()
        data["known_devices"] = {
            addr: {
                "custom_name": d.custom_name,
                "phone_number": d.phone_number,
                "is_primary": d.is_primary,
                "last_connected": d.last_connected,
            }
            for addr, d in self._devices.items()
        }
        _save(data)

    # ── Queries ──────────────────────────────────────────────

    def all_devices(self) -> list:
        return sorted(self._devices.values(),
                      key=lambda d: (not d.is_primary, d.custom_name or d.address))

    def get(self, address: str) -> Optional[KnownDevice]:
        return self._devices.get(address)

    def primary(self) -> Optional[KnownDevice]:
        for d in self._devices.values():
            if d.is_primary:
                return d
        return None

    def display_name(self, address: str, fallback: str = "") -> str:
        d = self._devices.get(address)
        if d and d.custom_name:
            return d.custom_name
        return fallback or address

    # ── Mutations ────────────────────────────────────────────

    def register(self, address: str, default_name: str = "") -> KnownDevice:
        """ודא שהמכשיר קיים ברשימה, ייצור רשומה חדשה אם צריך"""
        if address not in self._devices:
            self._devices[address] = KnownDevice(
                address=address, custom_name=default_name)
            if not self.primary():
                self._devices[address].is_primary = True
            self._persist()
        return self._devices[address]

    def rename(self, address: str, name: str):
        d = self.register(address)
        d.custom_name = name.strip()
        self._persist()

    def set_phone_number(self, address: str, number: str):
        d = self.register(address)
        d.phone_number = number
        self._persist()

    def set_primary(self, address: str):
        self.register(address)
        for addr, d in self._devices.items():
            d.is_primary = (addr == address)
        self._persist()

    def touch_connected(self, address: str):
        import time
        d = self.register(address)
        d.last_connected = time.time()
        self._persist()

    def remove(self, address: str):
        if address in self._devices:
            was_primary = self._devices[address].is_primary
            del self._devices[address]
            if was_primary and self._devices:
                # promote the most-recently-connected remaining device
                nxt = max(self._devices.values(), key=lambda d: d.last_connected)
                nxt.is_primary = True
            self._persist()
