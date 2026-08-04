#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ניהול מגש המערכת — System Tray"""

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtCore import Qt, QObject
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont

APP_VERSION = "1.0"


def _make_tray_icon(color: str = "#1A3A5C") -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(6, 6, 52, 52, 10, 10)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "כ")
    painter.end()
    return QIcon(pixmap)


class TrayManager(QObject):
    def __init__(self, main_window, bt_manager, app: QApplication, language_manager=None):
        super().__init__(app)
        self.main_window = main_window
        self.bt = bt_manager
        self.app = app
        self.lang_mgr = language_manager

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(_make_tray_icon())

        self._build_menu()
        if self.lang_mgr:
            self.lang_mgr.language_applied.connect(lambda _l: self._build_menu())

        self.tray.activated.connect(self._on_tray_activated)

        self.bt.call_incoming.connect(self._on_incoming)
        self.bt.device_connected.connect(self._on_connected)
        self.bt.device_disconnected.connect(self._on_disconnected)

        self.tray.show()

    def _t(self, he: str, en: str) -> str:
        if self.lang_mgr is not None and not self.lang_mgr.is_rtl:
            return en
        return he

    def _build_menu(self):
        app_name = self.lang_mgr.app_name if self.lang_mgr else self._t("פלאפון כשר חכם", "Smart Kosher Phone")
        self.tray.setToolTip(f"{app_name} v{APP_VERSION}")

        menu = QMenu()
        menu.setLayoutDirection(self.lang_mgr.direction if self.lang_mgr else Qt.LayoutDirection.RightToLeft)

        act_show = menu.addAction(self._t(f"פתח {app_name}", f"Open {app_name}"))
        act_show.triggered.connect(self._show_window)

        menu.addSeparator()

        act_scan = menu.addAction(self._t("סרוק מכשירי בלוטוס", "Scan Bluetooth Devices"))
        act_scan.triggered.connect(self.bt.scan_devices)

        act_demo = menu.addAction(self._t("הדגמה — שיחה נכנסת", "Demo — Incoming Call"))
        act_demo.triggered.connect(
            lambda: self.bt.simulate_incoming_call("0501234567", self._t("אבא", "Dad")))

        menu.addSeparator()

        act_quit = menu.addAction(self._t("יציאה", "Exit"))
        act_quit.triggered.connect(self.app.quit)

        self.tray.setContextMenu(menu)

    def _show_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _on_incoming(self, call_info):
        if hasattr(self, 'tray'):
            name = call_info.name or call_info.number
            self.tray.showMessage(
                self._t("שיחה נכנסת", "Incoming Call"),
                self._t(f"מתקשר: {name}", f"Caller: {name}"),
                QSystemTrayIcon.MessageIcon.Information,
                5000
            )
            self.tray.setIcon(_make_tray_icon("#C62828"))

    def _on_connected(self, device):
        if hasattr(self, 'tray'):
            self.tray.setIcon(_make_tray_icon("#2E7D32"))
            app_name = self.lang_mgr.app_name if self.lang_mgr else self._t("פלאפון כשר חכם", "Smart Kosher Phone")
            self.tray.showMessage(
                app_name,
                self._t(f"מחובר: {device.name}", f"Connected: {device.name}"),
                QSystemTrayIcon.MessageIcon.Information, 3000)

    def _on_disconnected(self, addr):
        if hasattr(self, 'tray'):
            self.tray.setIcon(_make_tray_icon("#1A3A5C"))
