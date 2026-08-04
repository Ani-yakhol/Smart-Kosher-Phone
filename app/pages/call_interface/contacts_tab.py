#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""דף אנשי קשר"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QDialog, QFormLayout, QDialogButtonBox,
    QFileDialog, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QSize
from PyQt6.QtGui import QFont

from app.core.language_manager import Translatable


class AddContactDialog(QDialog, Translatable):
    def __init__(self, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.setWindowTitle(self.t("הוסף איש קשר", "Add Contact"))
        self.setLayoutDirection(language_manager.direction)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.tr_set(self.name_input, "שם איש הקשר", "Contact name", setter="setPlaceholderText")
        self.name_label = QLabel()
        self.tr_set(self.name_label, "שם:", "Name:")
        form.addRow(self.name_label, self.name_input)

        self.number_input = QLineEdit()
        self.tr_set(self.number_input, "מספר טלפון", "Phone number", setter="setPlaceholderText")
        self.number_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.number_label = QLabel()
        self.tr_set(self.number_label, "מספר:", "Number:")
        form.addRow(self.number_label, self.number_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return self.number_input.text().strip(), self.name_input.text().strip()


class ContactItem(QWidget, Translatable):
    def __init__(self, number: str, name: str, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.number = number
        self.name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        # Avatar letter
        letter = name[0] if name else "#"
        avatar = QLabel(letter.upper())
        avatar.setObjectName("contactAvatar")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(avatar)

        layout.addSpacing(10)

        info = QVBoxLayout()
        name_lbl = QLabel(name or number)
        name_lbl.setObjectName("contactName")
        name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        info.addWidget(name_lbl)

        num_lbl = QLabel(number)
        num_lbl.setObjectName("contactNumber")
        num_lbl.setFont(QFont("Segoe UI", 10))
        num_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        info.addWidget(num_lbl)

        layout.addLayout(info, 1)

        self.dial_btn = QPushButton("📞")
        self.dial_btn.setObjectName("contactDialBtn")
        self.dial_btn.setFixedSize(40, 40)
        self.dial_btn.setFont(QFont("Segoe UI Emoji", 16))
        self.dial_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.dial_btn)


class ContactsTab(QWidget, Translatable):
    dial_requested = Signal(str)

    def __init__(self, bt_manager, language_manager, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.bt = bt_manager
        self.setObjectName("contactsPage")
        self.setLayoutDirection(language_manager.direction)
        self._contacts_widgets: list[ContactItem] = []
        self._build()
        self._load_sample_contacts()
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self.retranslate()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel()
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tr_set(title, "👥 אנשי קשר", "👥 Contacts")
        layout.addWidget(title)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.tr_set(self.search_input, "🔍 חיפוש...", "🔍 Search...", setter="setPlaceholderText")
        self.search_input.setMinimumHeight(40)
        self.search_input.textChanged.connect(self._filter)
        layout.addWidget(self.search_input)

        # List
        self.contact_list = QListWidget()
        self.contact_list.setObjectName("contactList")
        self.contact_list.setSpacing(3)
        layout.addWidget(self.contact_list, 1)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton()
        self.tr_set(self.btn_add, "➕ הוסף", "➕ Add")
        self.btn_add.setObjectName("secondaryButton")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.clicked.connect(self._add_contact)
        btn_row.addWidget(self.btn_add)

        self.btn_import = QPushButton()
        self.tr_set(self.btn_import, "📁 ייבא CSV", "📁 Import CSV")
        self.btn_import.setObjectName("secondaryButton")
        self.btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_import.clicked.connect(self._import_contacts)
        btn_row.addWidget(self.btn_import)
        layout.addLayout(btn_row)

    def _load_sample_contacts(self):
        samples_he = [
            ("0501234567", "אבא"),
            ("0521234567", "אמא"),
            ("0531234567", "דוד יוסי"),
            ("0541234567", "משרד"),
            ("0551234567", "רופא המשפחה"),
        ]
        samples_en = [
            ("0501234567", "Dad"),
            ("0521234567", "Mom"),
            ("0531234567", "Uncle Joe"),
            ("0541234567", "Office"),
            ("0551234567", "Family Doctor"),
        ]
        samples = samples_he if self._lang_mgr.is_rtl else samples_en
        for number, name in samples:
            self.bt.add_contact(number, name)
            self._add_contact_to_list(number, name)

    def _add_contact_to_list(self, number: str, name: str):
        item = QListWidgetItem()
        widget = ContactItem(number, name, self._lang_mgr)
        widget.dial_btn.clicked.connect(
            lambda _, n=number: self.dial_requested.emit(n))
        item.setSizeHint(QSize(0, 68))
        self.contact_list.addItem(item)
        self.contact_list.setItemWidget(item, widget)
        self._contacts_widgets.append(widget)

    def _filter(self, text: str):
        text = text.lower()
        for i in range(self.contact_list.count()):
            item = self.contact_list.item(i)
            widget = self.contact_list.itemWidget(item)
            if widget and isinstance(widget, ContactItem):
                visible = (text in widget.name.lower() or
                           text in widget.number)
                item.setHidden(not visible)

    def _add_contact(self):
        dlg = AddContactDialog(self._lang_mgr, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            number, name = dlg.get_data()
            if number:
                self.bt.add_contact(number, name)
                self._add_contact_to_list(number, name)

    def _import_contacts(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.t("בחר קובץ CSV", "Select CSV File"), "", "CSV Files (*.csv)")
        if path:
            self.bt.load_contacts_from_file(path)
            self.contact_list.clear()
            self._contacts_widgets.clear()
            for number, name in self.bt.get_contacts().items():
                self._add_contact_to_list(number, name)
