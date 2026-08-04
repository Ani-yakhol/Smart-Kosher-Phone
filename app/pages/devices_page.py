#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""דף מכשירים - ניהול חיבור בלוטוס, מכשירים מרובים, וזיהוי מספר טלפון"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QFrame, QProgressBar, QLineEdit, QTabWidget
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

from app.bluetooth_manager import BluetoothManager, BluetoothDevice
from app.core.device_registry import DeviceRegistry
from app.core.language_manager import Translatable


class DeviceItem(QWidget, Translatable):
    """שורת מכשיר ברשימת הסריקה — עם שם, כתובת וסטטוס"""

    def __init__(self, device: BluetoothDevice, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.device = device
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        info_layout = QVBoxLayout()
        name_lbl = QLabel(device.name)
        name_lbl.setObjectName("deviceName")
        name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        info_layout.addWidget(name_lbl)

        addr_lbl = QLabel(device.address)
        addr_lbl.setObjectName("deviceAddr")
        addr_lbl.setFont(QFont("Segoe UI", 9))
        addr_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        info_layout.addWidget(addr_lbl)

        layout.addLayout(info_layout)
        layout.addStretch()

        self.status_lbl = QLabel()
        self.status_lbl.setObjectName("deviceStatus")
        self.status_lbl.setFont(QFont("Segoe UI", 10))
        if device.connected:
            self.tr_set(self.status_lbl, "✅ מחובר", "✅ Connected")
        elif device.paired:
            self.tr_set(self.status_lbl, "🔗 מותאם", "🔗 Paired")
        else:
            self.status_lbl.setText("📡")
        layout.addWidget(self.status_lbl)


class KnownDeviceRow(QWidget, Translatable):
    """שורה ברשימת המכשירים המוכרים — שם ניתן לעריכה, מספר טלפון, מתג ראשי"""

    def __init__(self, dev, language_manager, on_rename, on_set_primary, on_remove, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.address = dev.address

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        self.star_btn = QPushButton("★" if dev.is_primary else "☆")
        self.star_btn.setObjectName("primaryStarBtn")
        self.star_btn.setFixedWidth(30)
        self.star_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tr_set(self.star_btn, "סמן כמכשיר ראשי", "Set as primary device", setter="setToolTip")
        self.star_btn.clicked.connect(lambda: on_set_primary(dev.address))
        layout.addWidget(self.star_btn)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        self.name_edit = QLineEdit(dev.custom_name or dev.address)
        self.name_edit.setObjectName("deviceNameEdit")
        self.name_edit.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.name_edit.editingFinished.connect(
            lambda: on_rename(dev.address, self.name_edit.text()))
        info_col.addWidget(self.name_edit)

        sub_row = QHBoxLayout()
        sub_row.setSpacing(10)
        addr_lbl = QLabel(dev.address)
        addr_lbl.setObjectName("deviceAddr")
        addr_lbl.setFont(QFont("Segoe UI", 8))
        addr_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        sub_row.addWidget(addr_lbl)

        self.number_lbl = QLabel()
        self.number_lbl.setObjectName("deviceNumber")
        self.number_lbl.setFont(QFont("Segoe UI", 8))
        self.number_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._set_number(dev.phone_number)
        sub_row.addWidget(self.number_lbl)
        sub_row.addStretch()
        info_col.addLayout(sub_row)

        layout.addLayout(info_col, 1)

        self.remove_btn = QPushButton("✕")
        self.remove_btn.setObjectName("removeDeviceBtn")
        self.remove_btn.setFixedWidth(28)
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tr_set(self.remove_btn, "הסר מהרשימה", "Remove from list", setter="setToolTip")
        self.remove_btn.clicked.connect(lambda: on_remove(dev.address))
        layout.addWidget(self.remove_btn)

    def _set_number(self, number: str):
        if number:
            self.number_lbl.setText(f"📞 {number}")
        else:
            self.tr_set(self.number_lbl, "מספר טרם זוהה", "Number not yet identified")

    def set_phone_number(self, number: str):
        self._set_number(number)

    def set_primary(self, is_primary: bool):
        self.star_btn.setText("★" if is_primary else "☆")


class DevicesPage(QWidget, Translatable):
    def __init__(self, bt_manager: BluetoothManager, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.bt = bt_manager
        self.registry = DeviceRegistry()
        self.setObjectName("devicesPage")
        self.setLayoutDirection(language_manager.direction)
        self._scan_items: dict[str, QListWidgetItem] = {}
        self._known_rows: dict[str, KnownDeviceRow] = {}
        self._build()
        self._connect_signals()

        language_manager.language_applied.connect(lambda _l: self._on_lang())

    # ── UI ────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Title
        self.title = QLabel()
        self.title.setObjectName("pageTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tr_set(self.title, "📡 מכשירי בלוטוס", "📡 Bluetooth Devices")
        layout.addWidget(self.title)

        # Connected device banner
        self.connected_banner = QFrame()
        self.connected_banner.setObjectName("connectedBanner")
        self.connected_banner.setVisible(False)
        banner_layout = QHBoxLayout(self.connected_banner)
        self.banner_icon = QLabel("🔗")
        self.banner_icon.setFont(QFont("Segoe UI Emoji", 18))
        banner_layout.addWidget(self.banner_icon)
        self.banner_text = QLabel("")
        self.banner_text.setObjectName("bannerText")
        self.banner_text.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        banner_layout.addWidget(self.banner_text)
        banner_layout.addStretch()
        self.btn_disconnect = QPushButton()
        self.tr_set(self.btn_disconnect, "נתק", "Disconnect")
        self.btn_disconnect.setObjectName("smallButton")
        self.btn_disconnect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_disconnect.clicked.connect(self.bt.disconnect_device)
        banner_layout.addWidget(self.btn_disconnect)
        layout.addWidget(self.connected_banner)

        # ── Tabs: Known devices (multi-device) / Scan for new ──
        self.tabs = QTabWidget()
        self.tabs.setObjectName("deviceSubTabs")

        # -- Known devices tab --
        known_page = QWidget()
        kl = QVBoxLayout(known_page)
        kl.setContentsMargins(4, 10, 4, 4)
        kl.setSpacing(8)

        self.known_info = QLabel()
        self.known_info.setObjectName("infoLabel")
        self.known_info.setWordWrap(True)
        self.tr_set(self.known_info,
            "המכשיר המסומן ★ הוא המכשיר הראשי — הוא ישמש כברירת מחדל לחיוג "
            "ולפונקציות השונות. מספר הטלפון מזוהה אוטומטית עם החיבור (אם הפלאפון תומך).",
            "The device marked ★ is the primary device — used by default for "
            "dialing and the app's various functions. The phone number is "
            "identified automatically on connection (if the phone supports it).")
        kl.addWidget(self.known_info)

        self.known_list = QListWidget()
        self.known_list.setObjectName("knownDeviceList")
        self.known_list.setSpacing(4)
        kl.addWidget(self.known_list, 1)

        self.tr_tab(self.tabs, self.tabs.addTab(known_page, ""), "מכשירים מוכרים", "Known Devices")

        # -- Scan tab --
        scan_page = QWidget()
        sl = QVBoxLayout(scan_page)
        sl.setContentsMargins(4, 10, 4, 4)
        sl.setSpacing(10)

        scan_row = QHBoxLayout()
        self.btn_scan = QPushButton()
        self.tr_set(self.btn_scan, "🔍  סרוק מכשירים", "🔍  Scan for Devices")
        self.btn_scan.setObjectName("primaryButton")
        self.btn_scan.setMinimumHeight(44)
        self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.clicked.connect(self._start_scan)
        scan_row.addWidget(self.btn_scan)

        self.btn_demo = QPushButton()
        self.tr_set(self.btn_demo, "הדגמה", "Demo")
        self.btn_demo.setObjectName("secondaryButton")
        self.btn_demo.setMinimumHeight(44)
        self.btn_demo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_demo.clicked.connect(self._enable_demo)
        scan_row.addWidget(self.btn_demo)
        sl.addLayout(scan_row)

        self.progress = QProgressBar()
        self.progress.setObjectName("scanProgress")
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(4)
        sl.addWidget(self.progress)

        self.list_label = QLabel()
        self.list_label.setObjectName("sectionLabel")
        self.tr_set(self.list_label, "מכשירים שנמצאו:", "Devices found:")
        sl.addWidget(self.list_label)

        self.device_list = QListWidget()
        self.device_list.setObjectName("deviceList")
        self.device_list.setSpacing(4)
        self.device_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        sl.addWidget(self.device_list, 1)

        self.btn_connect = QPushButton()
        self.tr_set(self.btn_connect, "🔗  התחבר למכשיר הנבחר", "🔗  Connect to Selected Device")
        self.btn_connect.setObjectName("primaryButton")
        self.btn_connect.setMinimumHeight(48)
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.setEnabled(False)
        self.btn_connect.clicked.connect(self._connect_selected)
        sl.addWidget(self.btn_connect)

        self.info = QLabel()
        self.info.setObjectName("infoLabel")
        self.info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tr_set(self.info,
            "💡 הכפל-לחיצה על מכשיר לחיבור מהיר\nהפלאפון חייב להיות מותאם (paired) מראש",
            "💡 Double-click a device to connect quickly\nThe phone must be paired in advance")
        sl.addWidget(self.info)

        self.tr_tab(self.tabs, self.tabs.addTab(scan_page, ""), "סריקה", "Scan")

        layout.addWidget(self.tabs, 1)

        self._refresh_known_list()

    def _connect_signals(self):
        self.bt.device_found.connect(self._on_device_found)
        self.bt.scan_finished.connect(self._on_scan_finished)
        self.bt.device_connected.connect(self._on_device_connected)
        self.bt.device_disconnected.connect(self._on_device_disconnected)
        self.bt.device_number_resolved.connect(self._on_number_resolved)
        self.device_list.currentRowChanged.connect(
            lambda r: self.btn_connect.setEnabled(r >= 0))

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self.retranslate()

    # ── Known devices (multi-device) ───────────────────────

    def _refresh_known_list(self):
        self.known_list.clear()
        self._known_rows.clear()
        for dev in self.registry.all_devices():
            item = QListWidgetItem()
            row = KnownDeviceRow(dev, self._lang_mgr, self._rename_device,
                                  self._set_primary_device, self._remove_device)
            item.setSizeHint(QSize(0, 58))
            self.known_list.addItem(item)
            self.known_list.setItemWidget(item, row)
            self._known_rows[dev.address] = row

    def _rename_device(self, address: str, name: str):
        self.registry.rename(address, name)

    def _set_primary_device(self, address: str):
        self.registry.set_primary(address)
        for addr, row in self._known_rows.items():
            row.set_primary(addr == address)

    def _remove_device(self, address: str):
        self.registry.remove(address)
        self._refresh_known_list()

    def _on_number_resolved(self, address: str, number: str):
        self.registry.set_phone_number(address, number)
        row = self._known_rows.get(address)
        if row:
            row.set_phone_number(number)

    # ── Scanning ────────────────────────────────────────────

    def _start_scan(self):
        self.device_list.clear()
        self._scan_items.clear()
        self.progress.setVisible(True)
        self.btn_scan.setEnabled(False)
        self.bt.scan_devices()

    def _enable_demo(self):
        self.device_list.clear()
        self._scan_items.clear()
        self.progress.setVisible(True)
        self.btn_scan.setEnabled(False)
        self.bt.enable_simulation()

    def _on_device_found(self, device: BluetoothDevice):
        item = QListWidgetItem()
        widget = DeviceItem(device, self._lang_mgr)
        item.setSizeHint(QSize(0, 68))
        self.device_list.addItem(item)
        self.device_list.setItemWidget(item, widget)
        self._scan_items[device.address] = item

    def _on_scan_finished(self, devices):
        self.progress.setVisible(False)
        self.btn_scan.setEnabled(True)

    def _on_item_double_clicked(self, item):
        widget = self.device_list.itemWidget(item)
        if widget and hasattr(widget, 'device'):
            self.bt.connect_device(widget.device.address)

    def _connect_selected(self):
        item = self.device_list.currentItem()
        if item:
            widget = self.device_list.itemWidget(item)
            if widget and hasattr(widget, 'device'):
                self.bt.connect_device(widget.device.address)

    # ── Connection state ────────────────────────────────────

    def _on_device_connected(self, device: BluetoothDevice):
        self.registry.register(device.address, device.name)
        self.registry.touch_connected(device.address)
        self.connected_banner.setVisible(True)
        display_name = self.registry.display_name(device.address, device.name)
        self.banner_text.setText(self.t("מחובר: ", "Connected: ") + display_name)
        self._refresh_known_list()

    def _on_device_disconnected(self, address: str):
        self.connected_banner.setVisible(False)

    def connect_primary_if_any(self):
        """נסה להתחבר אוטומטית למכשיר הראשי בהפעלת התוכנה (ברקע, לא חוסם)"""
        primary = self.registry.primary()
        if primary:
            self.bt.connect_device(primary.address)
