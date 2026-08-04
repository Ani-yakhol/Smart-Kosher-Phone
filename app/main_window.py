#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MainWindow v1.0 — שפה מיידית + בייביסיטר + לוגו SVG + מכשירים מרובים + toggles"""

import time
import os
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QTabWidget, QFrame, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

from app.bluetooth_manager import BluetoothManager, CallInfo
from app.core.recording_manager import RecordingManager
from app.core.voicemail_manager import VoicemailManager
from app.core.call_log import CallLog
from app.core.voice_recognizer import VoiceRecognizer
from app.core.language_manager import LanguageManager
from app.core.babysitter_engine import BabysitterEngine
from app.core.smart_home_engine import SmartHomeEngine
from app.core.service_toggles import ServiceToggles
from app.theme_manager import ThemeManager

from app.pages.call_interface.dialer_tab        import DialerTab
from app.pages.call_interface.active_call_tab   import ActiveCallTab
from app.pages.call_interface.contacts_tab      import ContactsTab
from app.pages.call_interface.recordings_tab    import RecordingsTab
from app.pages.call_interface.call_settings_tab import CallSettingsTab
from app.pages.call_interface.call_log_tab      import CallLogTab
from app.pages.devices_page                     import DevicesPage
from app.pages.voicemail.voicemail_page         import VoicemailPage
from app.pages.messaging.messaging_page         import MessagingPage
from app.pages.babysitter.babysitter_page       import BabysitterPage
from app.pages.smarthome.smart_home_page        import SmartHomePage
from app.pages.settings_page_main               import SettingsPageMain
from app.pages.stub_page                        import StubPage
from app.pages.about_page                       import AboutPage

from app.widgets.side_nav            import SideNav
from app.widgets.status_bar_widget   import StatusBarWidget
from app.widgets.incoming_popup      import IncomingCallPopup
from app.widgets.togglable_page      import TogglablePage

APP_VERSION = "1.0"


class MainWindow(QMainWindow):
    PAGE_CALL      = 0
    PAGE_DEVICES   = 1
    PAGE_VOICEMAIL = 2
    PAGE_BABYSIT   = 3
    PAGE_IVR       = 4
    PAGE_MESSAGING = 5
    PAGE_SMARTHOME = 6
    PAGE_MYPC      = 7
    PAGE_SETTINGS  = 8
    PAGE_ABOUT     = 9

    def __init__(self, bluetooth_manager: BluetoothManager,
                 theme_manager: ThemeManager,
                 language_manager: LanguageManager,
                 parent=None):
        super().__init__(parent)
        self.bt       = bluetooth_manager
        self.theme_mgr = theme_manager
        self.lang_mgr  = language_manager
        self.service_toggles = ServiceToggles(self)
        self._call_info: Optional[CallInfo] = None

        self.rec_mgr    = RecordingManager()
        self.vm_mgr     = VoicemailManager(recording_manager=self.rec_mgr,
                                            bt_manager=self.bt,
                                            language_manager=self.lang_mgr)
        self.call_log   = CallLog()
        self.voice_rec  = VoiceRecognizer(language_manager=self.lang_mgr)
        self.baby_engine = BabysitterEngine(bt_manager=self.bt,
                                             language_manager=self.lang_mgr)
        self.smarthome_engine = SmartHomeEngine(bt_manager=self.bt,
                                                 language_manager=self.lang_mgr)

        self._setup_window()
        self._build_ui()
        self._connect_signals()

    def _t(self, he: str, en: str) -> str:
        return he if self.lang_mgr.is_rtl else en

    def _setup_window(self):
        name = self.lang_mgr.app_name
        self.setWindowTitle(f"{name} v{APP_VERSION}")
        self.setMinimumSize(860, 620)
        self.resize(1080, 740)
        self.setLayoutDirection(self.lang_mgr.direction)
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "icon_256.png")
        icon = QIcon(icon_path)
        if not icon.isNull():
            self.setWindowIcon(icon)
        geo = QApplication.primaryScreen().geometry()
        self.move((geo.width()-1080)//2, (geo.height()-740)//2)

    def _build_ui(self):
        central = QWidget(); central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root_v = QVBoxLayout(central)
        root_v.setContentsMargins(0,0,0,0); root_v.setSpacing(0)

        self.status_bar_widget = StatusBarWidget(self.bt, self.lang_mgr)
        root_v.addWidget(self.status_bar_widget)

        # Body: internally always LTR — physical left/right order of
        # page_stack vs. side_nav is controlled explicitly by
        # _apply_nav_side() below, so it can flip per language:
        # side_nav stays on the RIGHT for Hebrew (RTL) and moves to the
        # LEFT for English (LTR), matching each language's natural reading
        # direction for a navigation rail.
        self.body = QWidget(); self.body.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.body_h = QHBoxLayout(self.body)
        self.body_h.setContentsMargins(0,0,0,0); self.body_h.setSpacing(0)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        self.page_stack.setLayoutDirection(self.lang_mgr.direction)

        self.vdiv = QFrame(); self.vdiv.setObjectName("sideNavVDivider")
        self.vdiv.setFrameShape(QFrame.Shape.VLine); self.vdiv.setFixedWidth(1)

        self.side_nav = SideNav(
            app_name=self.lang_mgr.app_name, version=f"v{APP_VERSION}")

        self._apply_nav_side()

        root_v.addWidget(self.body, 1)
        self.statusBar().setObjectName("mainStatusBar")
        self.statusBar().showMessage(
            f"{self.lang_mgr.app_name} v{APP_VERSION} " + self._t("מוכן", "Ready"))

        # ── Pages ──
        self._build_call_page()
        self.devices_page    = DevicesPage(self.bt, self.lang_mgr)
        self.voicemail_page  = VoicemailPage(self.bt, self.vm_mgr, self.rec_mgr, self.lang_mgr)
        self.babysitter_page = BabysitterPage(self.bt, self.baby_engine, self.lang_mgr)
        self.messaging_page  = MessagingPage(self.bt, self.lang_mgr)
        self.settings_page   = SettingsPageMain(
            language_manager=self.lang_mgr,
            theme_manager=self.theme_mgr,
            main_window=self)
        self.about_page      = AboutPage(self.lang_mgr)

        self.smarthome_page = SmartHomePage(self.bt, self.smarthome_engine, self.lang_mgr)

        self.ivr_stub = StubPage(self.lang_mgr, "קו תכנים", "IVR Line",
            "תפריטים קוליים IVR, ניתוב שיחות",
            "IVR voice menus, call routing")
        self.mypc_stub = StubPage(self.lang_mgr, "מחשב שלי", "My Computer",
            "גישה מרחוק, שיתוף קבצים, שליטה קולית",
            "Remote access, file sharing, voice control")

        # Wrap togglable pages with an on/off switch header.
        # Devices, Settings and About are intentionally excluded.
        self.call_toggle_wrap = TogglablePage(
            "call", "ממשק שיחה", "Call Interface", self._call_container,
            self.service_toggles, self.lang_mgr)
        self.voicemail_toggle_wrap = TogglablePage(
            "voicemail", "תא קולי", "Voicemail", self.voicemail_page,
            self.service_toggles, self.lang_mgr)
        self.babysitter_toggle_wrap = TogglablePage(
            "babysitter", "בייביסיטר", "Baby Monitor", self.babysitter_page,
            self.service_toggles, self.lang_mgr)
        self.ivr_toggle_wrap = TogglablePage(
            "ivr", "קו תכנים", "IVR Line", self.ivr_stub,
            self.service_toggles, self.lang_mgr)
        self.messaging_toggle_wrap = TogglablePage(
            "messaging", "הודעות", "Messages", self.messaging_page,
            self.service_toggles, self.lang_mgr)
        self.smarthome_toggle_wrap = TogglablePage(
            "smarthome", "בית חכם", "Smart Home", self.smarthome_page,
            self.service_toggles, self.lang_mgr)
        self.mypc_toggle_wrap = TogglablePage(
            "mypc", "מחשב שלי", "My Computer", self.mypc_stub,
            self.service_toggles, self.lang_mgr)

        self.page_stack.addWidget(self.call_toggle_wrap)        # 0
        self.page_stack.addWidget(self.devices_page)             # 1
        self.page_stack.addWidget(self.voicemail_toggle_wrap)    # 2
        self.page_stack.addWidget(self.babysitter_toggle_wrap)   # 3
        self.page_stack.addWidget(self.ivr_toggle_wrap)          # 4
        self.page_stack.addWidget(self.messaging_toggle_wrap)    # 5
        self.page_stack.addWidget(self.smarthome_toggle_wrap)    # 6
        self.page_stack.addWidget(self.mypc_toggle_wrap)         # 7
        self.page_stack.addWidget(self.settings_page)            # 8
        self.page_stack.addWidget(self.about_page)               # 9

        # ── Nav items (no emoji) ──
        labels = self.lang_mgr.nav_labels
        for lbl in labels:
            self.side_nav.add_nav_item(lbl)
        self._vm_nav_idx = 2
        self.side_nav.add_spacer()   # visual gap before settings/about
        self.side_nav.set_active(0)

        self._popup = IncomingCallPopup(self.lang_mgr)

        # Try connecting to the registered primary device automatically,
        # shortly after startup (non-blocking, silently falls back if
        # nothing is registered or the connection fails).
        QTimer.singleShot(600, self.devices_page.connect_primary_if_any)

    def _apply_nav_side(self):
        """Physically place side_nav on the right for Hebrew, left for English."""
        while self.body_h.count():
            self.body_h.takeAt(0)
        if self.lang_mgr.is_rtl:
            self.body_h.addWidget(self.page_stack, 1)
            self.body_h.addWidget(self.vdiv)
            self.body_h.addWidget(self.side_nav)
        else:
            self.body_h.addWidget(self.side_nav)
            self.body_h.addWidget(self.vdiv)
            self.body_h.addWidget(self.page_stack, 1)

    def _build_call_page(self):
        self._call_container = QWidget()
        self._call_container.setObjectName("callContainer")
        self._call_container.setLayoutDirection(self.lang_mgr.direction)
        ly = QVBoxLayout(self._call_container)
        ly.setContentsMargins(0,0,0,0); ly.setSpacing(0)

        self.call_tabs = QTabWidget()
        self.call_tabs.setObjectName("subTabsNorth")
        self.call_tabs.setLayoutDirection(self.lang_mgr.direction)
        self.call_tabs.setTabPosition(QTabWidget.TabPosition.North)

        self.dialer_tab        = DialerTab(self.bt, self.lang_mgr, self.rec_mgr)
        self.active_call_tab   = ActiveCallTab(self.bt, self.lang_mgr, self.rec_mgr)
        self.contacts_tab      = ContactsTab(self.bt, self.lang_mgr)
        self.call_log_tab      = CallLogTab(self.call_log, self.lang_mgr)
        self.recordings_tab    = RecordingsTab(self.rec_mgr, self.lang_mgr)
        self.call_settings_tab = CallSettingsTab(
            self.bt, self.lang_mgr, self.rec_mgr, self.voice_rec)

        for i, (widget, label) in enumerate(zip(
            [self.dialer_tab, self.active_call_tab, self.contacts_tab,
             self.call_log_tab, self.recordings_tab, self.call_settings_tab],
            self.lang_mgr.call_tab_labels
        )):
            self.call_tabs.addTab(widget, label)

        ly.addWidget(self.call_tabs)

    # ── Signals ───────────────────────────────────────────

    def _connect_signals(self):
        self.side_nav.page_changed.connect(self.page_stack.setCurrentIndex)
        self.status_bar_widget.theme_toggle_requested.connect(
            self._toggle_theme)
        self.theme_mgr.theme_changed.connect(self._on_theme_changed)

        # Language manager — applied immediately
        self.lang_mgr.language_applied.connect(self._on_language_applied)

        # BT
        self.bt.call_incoming.connect(self._on_incoming_call)
        self.bt.call_answered.connect(self._on_call_answered)
        self.bt.call_ended.connect(self._on_call_ended)
        self.bt.call_state_changed.connect(self._on_call_state_changed)
        self.bt.status_message.connect(self._on_status)
        self.bt.device_connected.connect(self.status_bar_widget.set_device)
        self.bt.device_disconnected.connect(
            lambda _: self.status_bar_widget.set_device(None))

        # Dialer / contacts / log
        self.dialer_tab.dial_requested.connect(self._initiate_call)
        self.contacts_tab.dial_requested.connect(self._initiate_call)
        self.call_log_tab.dial_requested.connect(self._initiate_call)

        # Active call
        self.active_call_tab.hangup_requested.connect(self._hangup)
        self.active_call_tab.answer_requested.connect(self._answer_call)
        self.active_call_tab.reject_requested.connect(self._reject_call)
        self.active_call_tab.vm_requested.connect(self._send_to_vm)

        # Popup
        self._popup.answered.connect(self._answer_call)
        self._popup.rejected.connect(self._reject_call)
        self._popup.silenced.connect(lambda: None)
        self._popup.sent_to_vm.connect(self._send_to_vm)

        # Voicemail
        self.vm_mgr.vm_message_saved.connect(
            lambda _: self._on_status(self._t("הודעה נשמרה בתא קולי", "Message saved to voicemail")))
        self.rec_mgr.recordings_changed.connect(self._update_vm_badge)

        # Voice DTMF
        self.voice_rec.digit_recognized.connect(self._on_voice_digit)

        # Babysitter
        self.baby_engine.alert_triggered.connect(
            lambda eid, ename: self._on_status(
                self._t(f"בייביסיטר: קול זוהה — {ename}", f"Baby Monitor: sound detected — {ename}")))
        self.baby_engine.call_initiated.connect(
            lambda n: self._on_status(self._t(f"בייביסיטר: מחייג {n}", f"Baby Monitor: dialing {n}")))
        self.bt.call_answered.connect(
            lambda ci: self.baby_engine.on_call_answered(ci.number))
        self.bt.call_ended.connect(
            lambda _: self.baby_engine.on_call_ended())

        # Smart home
        self.smarthome_page.dial_requested.connect(self._initiate_call)
        self.smarthome_engine.status_changed.connect(self._on_status)
        self.bt.call_answered.connect(self._on_smarthome_call_answered)

        # Multi-device: resolved phone numbers get pushed to the registry
        # via DevicesPage's own connection to bt.device_number_resolved.

    # ── Theme ─────────────────────────────────────────────

    def _toggle_theme(self):
        self.theme_mgr.toggle()

    def _on_theme_changed(self, theme: str):
        self.status_bar_widget.set_theme_label(theme)

    # ── Language — applied immediately ────────────────────

    def _on_language_applied(self, lang: str):
        """Called after LanguageManager.apply_language() runs"""
        direction = self.lang_mgr.direction
        self.setLayoutDirection(direction)
        self.setWindowTitle(f"{self.lang_mgr.app_name} v{APP_VERSION}")
        # page_stack content direction
        self.page_stack.setLayoutDirection(direction)
        self._call_container.setLayoutDirection(direction)
        self.call_tabs.setLayoutDirection(direction)
        # Update tab labels
        labels = self.lang_mgr.call_tab_labels
        for i in range(min(self.call_tabs.count(), len(labels))):
            self.call_tabs.setTabText(i, labels[i])
        # Update nav labels
        nav_labels = self.lang_mgr.nav_labels
        for i, btn in enumerate(self.side_nav._buttons):
            if i < len(nav_labels):
                btn.setText(nav_labels[i])
        self.side_nav.set_app_name(self.lang_mgr.app_name)
        # Flip side_nav physically left/right to match the new language
        self._apply_nav_side()
        # Status bar
        self.statusBar().showMessage(
            f"{self.lang_mgr.app_name} v{APP_VERSION} — " + self._t("שפה הוחלה", "Language applied"))

    # ── Status ────────────────────────────────────────────

    def _on_status(self, msg: str):
        self.status_bar_widget.set_message(msg)
        self.statusBar().showMessage(msg, 5000)

    def _update_vm_badge(self):
        unread = self.rec_mgr.unread_voicemail_count()
        self.side_nav.set_badge(self._vm_nav_idx, str(unread) if unread else "")

    # ── Voice DTMF ────────────────────────────────────────

    def _on_voice_digit(self, digit: str):
        if self.bt.current_call:
            self.bt.send_dtmf(digit)
            self._on_status(self._t(f"ספרה קולית נשלחה: {digit}", f"Voice digit sent: {digit}"))

    # ── Navigation ────────────────────────────────────────

    def _go_call(self, sub_widget=None):
        self.page_stack.setCurrentIndex(self.PAGE_CALL)
        self.side_nav.set_active(0)
        if sub_widget:
            self.call_tabs.setCurrentWidget(sub_widget)

    # ── Call handling ─────────────────────────────────────

    def _initiate_call(self, number: str):
        if not self.bt.is_connected:
            self._on_status(self._t("לא מחובר לפלאפון", "Not connected to a phone"))
            return
        name = self.bt.get_contacts().get(number, "")
        self.bt.dial(number)
        info = CallInfo(number=number, name=name,
                        direction="outgoing", status="ringing")
        self._call_info = info
        self.active_call_tab.start_call(info)
        self._go_call(self.active_call_tab)
        if self.rec_mgr.should_record(number):
            self.rec_mgr.start_recording(number, name, "outgoing")

    def _on_incoming_call(self, call_info: CallInfo):
        self._call_info = call_info

        # Blacklist check
        if self.call_log.is_blacklisted(call_info.number):
            self.bt.reject_call()
            self.call_log.add(call_info.number, call_info.name, "blacklist")
            self._on_status(self._t(f"מספר חסום: {call_info.number}", f"Blocked number: {call_info.number}"))
            return

        # Babysitter auto-answer — only if the Baby Monitor tab is enabled
        if (self.service_toggles.is_enabled("babysitter")
                and self.baby_engine.should_auto_answer(call_info.number)):
            self.bt.answer_call()
            self._on_status(self._t(
                f"בייביסיטר: מענה אוטומטי ל-{call_info.number}",
                f"Baby Monitor: auto-answering {call_info.number}"))
            return

        # Voicemail — only if the Voicemail tab is enabled
        if (self.service_toggles.is_enabled("voicemail")
                and self.vm_mgr.on_incoming_call(call_info.number, call_info.name)):
            self._on_status(self._t("תא קולי יענה לשיחה", "Voicemail will answer the call"))
            return

        # Show incoming in active_call tab
        self.active_call_tab.show_incoming(call_info)
        self._go_call(self.active_call_tab)

        if not self.isVisible() or self.isMinimized():
            self._popup.show_call(call_info)
        else:
            self.show(); self.raise_(); self.activateWindow()

        if self.rec_mgr.should_record(call_info.number):
            self.rec_mgr.start_recording(
                call_info.number, call_info.name, "incoming")

    def _answer_call(self):
        self._popup.close_popup(); self.vm_mgr.cancel()
        self.bt.answer_call()
        if self._call_info:
            self.call_log.add(self._call_info.number,
                              self._call_info.name, "incoming", answered=True)

    def _reject_call(self):
        self._popup.close_popup(); self.vm_mgr.cancel()
        self.bt.reject_call()
        self.active_call_tab.show_idle()
        if self._call_info:
            self.call_log.add(self._call_info.number,
                              self._call_info.name, "rejected")

    def _send_to_vm(self):
        self._popup.close_popup()
        if self._call_info:
            self.vm_mgr.on_incoming_call(
                self._call_info.number, self._call_info.name)
        self.active_call_tab.show_idle()

    def _on_call_answered(self, call_info: CallInfo):
        self._call_info = call_info
        self._popup.close_popup()
        self.active_call_tab.activate_call(call_info)
        self._go_call(self.active_call_tab)

    def _on_call_ended(self, call_info: CallInfo):
        dur = max(0.0, time.time() - (call_info.start_time or time.time()))
        self.call_log.add(call_info.number, call_info.name,
                          call_info.direction, duration=dur, answered=True)
        if self.rec_mgr.is_recording:
            self.rec_mgr.stop_recording()
        self.active_call_tab.end_call()

    def _on_call_state_changed(self, call_info: CallInfo):
        self._call_info = call_info
        if call_info.direction == "outgoing":
            self.active_call_tab.start_call(call_info)
            self._go_call(self.active_call_tab)

    def _hangup(self):
        self.bt.hangup()

    def _on_smarthome_call_answered(self, call_info: CallInfo):
        """אם השיחה שנענתה היא לקו הבית החכם ומוגדר להשמיע הכרזות אוטומטית — השמע אותן"""
        if not self.service_toggles.is_enabled("smarthome"):
            return
        hub_number = self.smarthome_engine.settings.hub_number
        if (hub_number and call_info.number and
                hub_number.replace(" ", "") == call_info.number.replace(" ", "") and
                self.smarthome_engine.settings.announce_on_connect):
            QTimer.singleShot(1500, self.smarthome_engine.announce_all)

    def closeEvent(self, event):
        self.baby_engine.stop_monitoring()
        event.ignore(); self.hide()
