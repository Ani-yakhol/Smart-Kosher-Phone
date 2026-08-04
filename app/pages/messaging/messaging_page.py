#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MessagingPage — לשונית התכתבות
שליחת וקבלת הודעות טקסט דרך שיחה טלפונית ע"י קידוד DTMF
"""

import datetime
from dataclasses import dataclass
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QFrame, QSplitter, QScrollArea, QSizePolicy, QComboBox,
    QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QTextCursor

from app.core.text_modem import TextModem
from app.core.language_manager import Translatable
from app.widgets.send_button import SendButton


@dataclass
class ChatMessage:
    text: str
    sender: str          # "me" | phone number
    timestamp: datetime.datetime
    read: bool = False
    direction: str = "sent"   # "sent" | "received"


class MessageBubble(QFrame):
    """בועת הודעה בצ'אט"""
    def __init__(self, msg: ChatMessage, parent=None):
        super().__init__(parent)
        is_mine = msg.direction == "sent"
        self.setObjectName("msgBubbleMine" if is_mine else "msgBubbleOther")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 3, 8, 3)

        if is_mine:
            outer.addStretch()

        card = QFrame()
        card.setObjectName("msgCardMine" if is_mine else "msgCardOther")
        card_ly = QVBoxLayout(card)
        card_ly.setContentsMargins(10, 6, 10, 6)
        card_ly.setSpacing(3)
        card.setMaximumWidth(420)

        text_lbl = QLabel(msg.text)
        text_lbl.setObjectName("msgText")
        text_lbl.setFont(QFont("Segoe UI", 11))
        text_lbl.setWordWrap(True)
        text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_ly.addWidget(text_lbl)

        time_str = msg.timestamp.strftime("%H:%M")
        status = "✓✓" if msg.read else "✓"
        meta = f"{time_str}  {status}" if is_mine else time_str
        meta_lbl = QLabel(meta)
        meta_lbl.setObjectName("msgMeta")
        meta_lbl.setFont(QFont("Segoe UI", 8))
        meta_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft if is_mine else Qt.AlignmentFlag.AlignRight)
        card_ly.addWidget(meta_lbl)

        outer.addWidget(card)
        if not is_mine:
            outer.addStretch()


class ChatView(QScrollArea):
    """אזור תצוגת הצ'אט"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setObjectName("chatView")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._content.setObjectName("chatContent")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(4, 8, 4, 8)
        self._layout.setSpacing(4)
        self._layout.addStretch()

        self.setWidget(self._content)

    def add_message(self, msg: ChatMessage):
        bubble = MessageBubble(msg)
        self._layout.addWidget(bubble)
        QTimer.singleShot(50, self._scroll_bottom)

    def clear_chat(self):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _scroll_bottom(self):
        vbar = self.verticalScrollBar()
        vbar.setValue(vbar.maximum())


class ConversationItem(QWidget):
    """פריט בקשר שיחה מתמשכת"""
    def __init__(self, number: str, name: str,
                 last_msg: str = "", unread: int = 0, parent=None):
        super().__init__(parent)
        self.number = number
        ly = QHBoxLayout(self)
        ly.setContentsMargins(10, 8, 10, 8)

        avatar = QLabel((name[0] if name else "#").upper())
        avatar.setObjectName("contactAvatar")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        ly.addWidget(avatar)

        info = QVBoxLayout(); info.setSpacing(2)
        top = QHBoxLayout()
        name_lbl = QLabel(name or number)
        name_lbl.setObjectName("contactName")
        name_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        top.addWidget(name_lbl)
        top.addStretch()
        if unread:
            badge = QLabel(str(unread))
            badge.setObjectName("sideNavBadge")
            badge.setFixedSize(20, 20)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            top.addWidget(badge)
        info.addLayout(top)

        msg_lbl = QLabel(last_msg[:50] if last_msg else "")
        msg_lbl.setObjectName("logDirLabel")
        msg_lbl.setFont(QFont("Segoe UI", 9))
        info.addWidget(msg_lbl)

        ly.addLayout(info, 1)


class MessagingPage(QWidget, Translatable):
    def __init__(self, bt_manager, language_manager, contacts: dict = None, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.bt = bt_manager
        self.contacts = contacts or {}   # number → name
        self.modem = TextModem(bt_manager=bt_manager, language_manager=language_manager)
        self.setObjectName("messagingPage")
        self.setLayoutDirection(language_manager.direction)

        # State
        self._current_number = ""
        self._conversations: dict[str, list[ChatMessage]] = {}
        self._typing_timer = QTimer(self)
        self._typing_timer.setSingleShot(True)
        self._typing_timer.timeout.connect(self._on_typing_stop)
        self._last_typed = False

        self._build()
        self._connect_signals()
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        # The send-arrow should point toward the "forward" direction of
        # reading — right in Hebrew (RTL), so we flip it for the mirror
        # feel; conventionally it just points up, which works in both.
        self.retranslate()
        if not self._current_number:
            self.chat_name_lbl.setText(self.t("בחר שיחה", "Select a conversation"))
        self._refresh_conv_list()

    # ── Build ─────────────────────────────────────────────

    def _build(self):
        main_ly = QVBoxLayout(self)
        main_ly.setContentsMargins(0, 0, 0, 0)
        main_ly.setSpacing(0)

        # Header
        header = QFrame(); header.setObjectName("pageHeader")
        h_ly = QHBoxLayout(header); h_ly.setContentsMargins(14, 10, 14, 10)
        title = QLabel()
        title.setObjectName("pageTitle")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.tr_set(title, "💬  התכתבות DTMF", "💬  DTMF Messaging")
        h_ly.addWidget(title); h_ly.addStretch()
        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("vmStateLbl")
        self.status_lbl.setFont(QFont("Segoe UI", 9))
        h_ly.addWidget(self.status_lbl)
        main_ly.addWidget(header)

        # Body: splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("msgSplitter")
        splitter.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        # LEFT PANEL — conversation list
        left = QWidget(); left.setObjectName("msgLeftPanel")
        left.setMinimumWidth(200); left.setMaximumWidth(280)
        left_ly = QVBoxLayout(left)
        left_ly.setContentsMargins(0, 0, 0, 0); left_ly.setSpacing(0)

        search = QLineEdit()
        search.setObjectName("searchInput")
        self.tr_set(search, "🔍 חפש איש קשר…", "🔍 Search contact…", setter="setPlaceholderText")
        search.setContentsMargins(8,8,8,8)
        left_ly.addWidget(search)

        self.conv_list = QListWidget()
        self.conv_list.setObjectName("callLogList")
        self.conv_list.currentRowChanged.connect(self._on_conv_selected)
        left_ly.addWidget(self.conv_list, 1)

        new_btn = QPushButton()
        self.tr_set(new_btn, "✏️  שיחה חדשה", "✏️  New Conversation")
        new_btn.setObjectName("primaryButton")
        new_btn.setMinimumHeight(40)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._new_conversation)
        left_ly.addWidget(new_btn)

        splitter.addWidget(left)

        # RIGHT PANEL — chat area
        right = QWidget(); right.setObjectName("msgRightPanel")
        right_ly = QVBoxLayout(right)
        right_ly.setContentsMargins(0, 0, 0, 0); right_ly.setSpacing(0)

        # Chat header bar
        self.chat_header = QFrame()
        self.chat_header.setObjectName("chatHeader")
        ch_ly = QHBoxLayout(self.chat_header)
        ch_ly.setContentsMargins(12, 8, 12, 8)
        self.chat_name_lbl = QLabel()
        self.chat_name_lbl.setObjectName("callName")
        self.chat_name_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.tr_set(self.chat_name_lbl, "בחר שיחה", "Select a conversation")
        ch_ly.addWidget(self.chat_name_lbl)
        ch_ly.addStretch()
        self.typing_lbl = QLabel("")
        self.typing_lbl.setObjectName("typingIndicator")
        self.typing_lbl.setFont(QFont("Segoe UI", 9))
        ch_ly.addWidget(self.typing_lbl)
        self.send_progress_lbl = QLabel("")
        self.send_progress_lbl.setObjectName("logDirLabel")
        self.send_progress_lbl.setFont(QFont("Segoe UI", 9))
        ch_ly.addWidget(self.send_progress_lbl)
        right_ly.addWidget(self.chat_header)

        # Chat view
        self.chat_view = ChatView()
        right_ly.addWidget(self.chat_view, 1)

        # Input bar
        input_frame = QFrame(); input_frame.setObjectName("msgInputBar")
        inp_ly = QHBoxLayout(input_frame)
        inp_ly.setContentsMargins(10, 8, 10, 8); inp_ly.setSpacing(8)

        self.text_input = QTextEdit()
        self.text_input.setObjectName("msgInput")
        self.text_input.setMaximumHeight(80)
        self.tr_set(self.text_input, "הקלד הודעה… (Enter לשליחה, Shift+Enter לשורה חדשה)",
                    "Type a message… (Enter to send, Shift+Enter for a new line)",
                    setter="setPlaceholderText")
        self.text_input.setFont(QFont("Segoe UI", 11))
        self.text_input.textChanged.connect(self._on_text_changed)
        inp_ly.addWidget(self.text_input, 1)

        # Modern circular chevron send button — transparent bg
        send_btn = SendButton(diameter=52)
        self.tr_set(send_btn, "שלח", "Send", setter="setToolTip")
        send_btn.clicked.connect(self._send_message)
        inp_ly.addWidget(send_btn)

        right_ly.addWidget(input_frame)

        splitter.addWidget(right)
        splitter.setSizes([220, 600])
        main_ly.addWidget(splitter, 1)

        # Bottom info bar
        info = QLabel()
        info.setObjectName("infoLabel")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setContentsMargins(0, 4, 0, 4)
        self.tr_set(info,
            "💡 ההתכתבות עובדת דרך שיחה טלפונית פעילה — "
            "חייג קודם למספר הרצוי, ואז שלח הודעות",
            "💡 Messaging works over an active phone call — "
            "dial the desired number first, then send messages")
        main_ly.addWidget(info)

    # ── Signal wiring ─────────────────────────────────────

    def _connect_signals(self):
        self.modem.message_received.connect(self._on_message_received)
        self.modem.typing_started.connect(self._on_remote_typing_start)
        self.modem.typing_stopped.connect(self._on_remote_typing_stop)
        self.modem.read_receipt.connect(self._on_read_receipt)
        self.modem.send_progress.connect(self._on_send_progress)
        self.modem.send_complete.connect(self._on_send_complete)
        self.modem.error_occurred.connect(
            lambda e: self.status_lbl.setText(f"⚠️ {e}"))

    # ── Conversation list ─────────────────────────────────

    def _refresh_conv_list(self):
        self.conv_list.clear()
        for number, msgs in self._conversations.items():
            name = self.contacts.get(number, number)
            last = msgs[-1].text if msgs else ""
            unread = sum(1 for m in msgs
                         if m.direction == "received" and not m.read)
            item = QListWidgetItem()
            w = ConversationItem(number, name, last, unread)
            item.setSizeHint(QSize(0, 64))
            item.setData(Qt.ItemDataRole.UserRole, number)
            self.conv_list.addItem(item)
            self.conv_list.setItemWidget(item, w)

    def _on_conv_selected(self, row: int):
        item = self.conv_list.item(row)
        if not item: return
        number = item.data(Qt.ItemDataRole.UserRole)
        self._open_conversation(number)

    def _open_conversation(self, number: str):
        self._current_number = number
        name = self.contacts.get(number, number)
        self.chat_name_lbl.setText(f"💬  {name}")
        self.chat_view.clear_chat()
        for msg in self._conversations.get(number, []):
            self.chat_view.add_message(msg)
            msg.read = True
        # Send read receipt
        if self.bt and self.bt.is_connected:
            self.modem.send_read_receipt()

    def _new_conversation(self):
        """פתח שיחה עם מספר חדש"""
        from PyQt6.QtWidgets import QInputDialog
        numbers = list(self.contacts.keys())
        names = [f"{self.contacts[n]}  ({n})" for n in numbers]
        names.append(self.t("מספר אחר…", "Other number…"))

        from PyQt6.QtWidgets import QDialog, QFormLayout, QComboBox, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle(self.t("שיחה חדשה", "New Conversation"))
        dlg.setLayoutDirection(self._lang_mgr.direction)
        dlg.setMinimumWidth(300)
        ly = QVBoxLayout(dlg)
        form = QFormLayout()
        combo = QComboBox()
        combo.addItems(names)
        form.addRow(self.t("בחר איש קשר:", "Choose a contact:"), combo)
        self.manual_num = QLineEdit()
        self.tr_set(self.manual_num, "הקלד מספר…", "Type a number…", setter="setPlaceholderText")
        self.manual_num.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        form.addRow(self.t("או הקלד מספר:", "Or type a number:"), self.manual_num)
        ly.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        ly.addWidget(btns)

        if dlg.exec():
            idx = combo.currentIndex()
            if idx < len(numbers):
                number = numbers[idx]
            else:
                number = self.manual_num.text().strip()
            if number:
                if number not in self._conversations:
                    self._conversations[number] = []
                self._refresh_conv_list()
                self._open_conversation(number)

    # ── Sending ───────────────────────────────────────────

    def _on_text_changed(self):
        if not self._current_number: return
        if not self._last_typed:
            self._last_typed = True
            self.modem.send_typing_start()
        self._typing_timer.start(3000)

    def _on_typing_stop(self):
        self._last_typed = False
        self.modem.send_typing_stop()

    def _send_message(self):
        text = self.text_input.toPlainText().strip()
        if not text or not self._current_number: return
        if not self.bt or not self.bt.is_connected:
            self.status_lbl.setText(self.t("⚠️ לא מחובר — חייג קודם", "⚠️ Not connected — dial first"))
            return

        # Stop typing indicator
        self._typing_timer.stop()
        if self._last_typed:
            self._last_typed = False
            self.modem.send_typing_stop()

        msg = ChatMessage(
            text=text,
            sender="me",
            timestamp=datetime.datetime.now(),
            direction="sent"
        )
        if self._current_number not in self._conversations:
            self._conversations[self._current_number] = []
        self._conversations[self._current_number].append(msg)
        self.chat_view.add_message(msg)
        self.text_input.clear()

        self.status_lbl.setText(self.t("שולח…", "Sending…"))
        self.modem.send_message(text)
        self._refresh_conv_list()

    def _on_send_progress(self, sent: int, total: int):
        pct = int(sent / max(total, 1) * 100)
        self.send_progress_lbl.setText(self.t(f"שולח… {pct}%", f"Sending… {pct}%"))

    def _on_send_complete(self):
        self.send_progress_lbl.setText("")
        self.status_lbl.setText(self.t("✓ נשלח", "✓ Sent"))
        QTimer.singleShot(3000, lambda: self.status_lbl.setText(""))

    # ── Receiving ─────────────────────────────────────────

    def _on_message_received(self, number: str, text: str):
        msg = ChatMessage(
            text=text,
            sender=number,
            timestamp=datetime.datetime.now(),
            direction="received",
            read=(number == self._current_number)
        )
        if number not in self._conversations:
            self._conversations[number] = []
        self._conversations[number].append(msg)

        if number == self._current_number:
            self.chat_view.add_message(msg)
            self.modem.send_read_receipt()

        self._refresh_conv_list()
        self.status_lbl.setText(self.t(
            f"📨 הודעה חדשה מ-{self.contacts.get(number, number)}",
            f"📨 New message from {self.contacts.get(number, number)}"))
        QTimer.singleShot(4000, lambda: self.status_lbl.setText(""))

    def _on_remote_typing_start(self, number: str):
        if number == self._current_number:
            name = self.contacts.get(number, number)
            self.typing_lbl.setText(self.t(f"✏️  {name} כותב…", f"✏️  {name} is typing…"))

    def _on_remote_typing_stop(self, number: str):
        if number == self._current_number:
            self.typing_lbl.setText("")

    def _on_read_receipt(self, number: str):
        if number in self._conversations:
            for msg in self._conversations[number]:
                if msg.direction == "sent":
                    msg.read = True
        self.status_lbl.setText(self.t("✓✓ נקרא", "✓✓ Read"))
        QTimer.singleShot(2000, lambda: self.status_lbl.setText(""))

    # ── Public API ────────────────────────────────────────

    def set_contacts(self, contacts: dict):
        self.contacts = contacts

    def on_dtmf_received(self, number: str, digit: str):
        """קרא מ-BluetoothManager כשמגיע DTMF"""
        self.modem.on_dtmf_received(number, digit)

    def keyPressEvent(self, event):
        from PyQt6.QtCore import Qt
        if (event.key() == Qt.Key.Key_Return and
                not event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self._send_message()
        else:
            super().keyPressEvent(event)
