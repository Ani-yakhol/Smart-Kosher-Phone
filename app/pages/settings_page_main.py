#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""הגדרות ראשיות v1.0 — ססמה + שפה עם החלה מיידית"""

import hashlib, json, os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QComboBox, QScrollArea,
    QDialog, QFormLayout, QDialogButtonBox, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtGui import QFont

from app.core.language_manager import Translatable, LanguageManager

SETTINGS_PATH = os.path.join(
    os.path.expanduser("~"), "BluePhone", "settings.json")


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


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


class PasswordDialog(QDialog):
    def __init__(self, title: str, prompt: str, is_rtl: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if is_rtl else Qt.LayoutDirection.LeftToRight)
        self.setMinimumWidth(300)
        ly = QVBoxLayout(self)
        ly.addWidget(QLabel(prompt))
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw.setPlaceholderText("הקלד ססמה…" if is_rtl else "Enter password…")
        ly.addWidget(self.pw)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        ly.addWidget(btns)
        self.pw.returnPressed.connect(self.accept)

    def password(self) -> str:
        return self.pw.text()


class SettingsPageMain(QWidget, Translatable):
    language_changed = Signal(str)   # "he" | "en" — immediate apply

    def __init__(self, language_manager, theme_manager=None,
                 main_window=None, parent=None):
        super().__init__(parent)
        self._init_translator(language_manager)
        self.theme_mgr = theme_manager
        self.lang_mgr  = language_manager
        self.main_win  = main_window
        self.setObjectName("settingsPage")
        self.setLayoutDirection(language_manager.direction)
        self._data = _load()
        self._build()
        language_manager.language_applied.connect(lambda _l: self._on_lang())

    def _on_lang(self):
        self.setLayoutDirection(self._lang_mgr.direction)
        self.retranslate()
        has_pw = bool(self._data.get("password_hash"))
        self.tr_set(self.pw_status, "ססמה מוגדרת" if has_pw else "ללא ססמה — התוכנה פתוחה",
                    "Password set" if has_pw else "No password — app is open")
        self.tr_set(self.btn_set_pw, "שנה ססמה" if has_pw else "הגדר ססמה",
                    "Change Password" if has_pw else "Set Password")

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True); scroll.setObjectName("settingsScroll")
        inner = QWidget(); inner.setObjectName("settingsContent")
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(scroll)

        ly = QVBoxLayout(inner)
        ly.setContentsMargins(24, 20, 24, 20); ly.setSpacing(18)

        title = QLabel(); title.setObjectName("pageTitle")
        self.tr_set(title, "הגדרות", "Settings")
        ly.addWidget(title)

        # ── Password ──
        pg = self._group("נעילת ססמה", "Password Lock")
        ply = QVBoxLayout()
        has_pw = bool(self._data.get("password_hash"))
        self.pw_status = QLabel()
        self.tr_set(self.pw_status, "ססמה מוגדרת" if has_pw else "ללא ססמה — התוכנה פתוחה",
                    "Password set" if has_pw else "No password — app is open")
        self.pw_status.setObjectName("infoLabel"); ply.addWidget(self.pw_status)
        pw_row = QHBoxLayout()
        self.btn_set_pw = QPushButton()
        self.tr_set(self.btn_set_pw, "שנה ססמה" if has_pw else "הגדר ססמה",
                    "Change Password" if has_pw else "Set Password")
        self.btn_set_pw.setObjectName("primaryButton")
        self.btn_set_pw.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_set_pw.clicked.connect(self._set_password)
        pw_row.addWidget(self.btn_set_pw)
        self.btn_del_pw = QPushButton()
        self.tr_set(self.btn_del_pw, "מחק ססמה", "Delete Password")
        self.btn_del_pw.setObjectName("secondaryButton")
        self.btn_del_pw.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del_pw.setEnabled(has_pw)
        self.btn_del_pw.clicked.connect(self._delete_password)
        pw_row.addWidget(self.btn_del_pw); pw_row.addStretch()
        ply.addLayout(pw_row)
        pg.setLayout(ply); ly.addWidget(pg)

        # ── Language — immediate apply ──
        lg = self._group("שפת ממשק", "Interface Language")
        lly = QVBoxLayout()
        lang_lbl = QLabel(); self.tr_set(lang_lbl, "בחר שפה (השינוי מיידי):", "Choose language (applies immediately):")
        lly.addWidget(lang_lbl)
        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("filterCombo")
        self.lang_combo.addItem("עברית (ימין לשמאל)", "he")
        self.lang_combo.addItem("English (left to right)", "en")
        current = self.lang_mgr.lang
        self.lang_combo.setCurrentIndex(0 if current == "he" else 1)
        lly.addWidget(self.lang_combo)

        apply_row = QHBoxLayout()
        btn_apply = QPushButton()
        self.tr_set(btn_apply, "החל שפה עכשיו", "Apply Language Now")
        btn_apply.setObjectName("primaryButton")
        btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_apply.clicked.connect(self._apply_language_now)
        apply_row.addWidget(btn_apply); apply_row.addStretch()
        lly.addLayout(apply_row)

        self.lang_status = QLabel("")
        self.lang_status.setObjectName("infoLabel"); lly.addWidget(self.lang_status)
        lg.setLayout(lly); ly.addWidget(lg)

        # ── Theme ──
        tg = self._group("ערכת נושא", "Theme")
        tly = QVBoxLayout()
        tr = QHBoxLayout()
        btn_light = QPushButton()
        self.tr_set(btn_light, "מצב בהיר", "Light Mode")
        btn_light.setObjectName("secondaryButton")
        btn_light.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_light.clicked.connect(
            lambda: self.theme_mgr and self.theme_mgr.apply("light"))
        btn_dark = QPushButton()
        self.tr_set(btn_dark, "מצב כהה", "Dark Mode")
        btn_dark.setObjectName("secondaryButton")
        btn_dark.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_dark.clicked.connect(
            lambda: self.theme_mgr and self.theme_mgr.apply("dark"))
        tr.addWidget(btn_light); tr.addWidget(btn_dark); tr.addStretch()
        tly.addLayout(tr)
        tg.setLayout(tly); ly.addWidget(tg)

        ly.addStretch()

    def _group(self, he: str, en: str) -> QGroupBox:
        g = QGroupBox(); g.setObjectName("settingsGroup")
        self.tr_set(g, he, en, setter="setTitle")
        g.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold)); return g

    # ── Password ──────────────────────────────────────────

    def _verify_current_password(self) -> bool:
        if not self._data.get("password_hash"):
            return True
        is_rtl = self._lang_mgr.is_rtl
        dlg = PasswordDialog(self.t("אימות", "Verify"),
                              self.t("הזן את הססמה הנוכחית:", "Enter your current password:"),
                              is_rtl, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        if _hash(dlg.password()) != self._data["password_hash"]:
            QMessageBox.warning(self, self.t("שגיאה", "Error"), self.t("ססמה שגויה", "Incorrect password"))
            return False
        return True

    def _set_password(self):
        if not self._verify_current_password():
            return
        is_rtl = self._lang_mgr.is_rtl
        d1 = PasswordDialog(self.t("ססמה חדשה", "New Password"),
                             self.t("הזן ססמה חדשה:", "Enter a new password:"), is_rtl, self)
        if d1.exec() != QDialog.DialogCode.Accepted or not d1.password():
            return
        d2 = PasswordDialog(self.t("אישור", "Confirm"),
                             self.t("הזן שוב לאישור:", "Re-enter to confirm:"), is_rtl, self)
        if d2.exec() != QDialog.DialogCode.Accepted:
            return
        if d1.password() != d2.password():
            QMessageBox.warning(self, self.t("שגיאה", "Error"),
                                 self.t("הססמאות אינן תואמות", "Passwords do not match"))
            return
        self._data["password_hash"] = _hash(d1.password())
        _save(self._data)
        self.tr_set(self.pw_status, "ססמה מוגדרת", "Password set")
        self.tr_set(self.btn_set_pw, "שנה ססמה", "Change Password")
        self.btn_del_pw.setEnabled(True)
        QMessageBox.information(self, self.t("הצלחה", "Success"), self.t("הססמה נשמרה", "Password saved"))

    def _delete_password(self):
        if not self._verify_current_password():
            return
        r = QMessageBox.question(self, self.t("מחיקה", "Delete"), self.t("למחוק ססמה?", "Delete password?"),
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self._data.pop("password_hash", None)
            _save(self._data)
            self.tr_set(self.pw_status, "ללא ססמה", "No password")
            self.tr_set(self.btn_set_pw, "הגדר ססמה", "Set Password")
            self.btn_del_pw.setEnabled(False)

    # ── Language — IMMEDIATE ──────────────────────────────

    def _apply_language_now(self):
        lang = self.lang_combo.currentData()
        if self.lang_mgr:
            self.lang_mgr.apply_language(lang, self.main_win)
            self.lang_status.setText(
                self.t(f"שפה הוחלה: {'עברית' if lang=='he' else 'English'}",
                        f"Language applied: {'Hebrew' if lang=='he' else 'English'}"))
        self.language_changed.emit(lang)

    # ── Static ────────────────────────────────────────────

    @staticmethod
    def verify_password_at_startup() -> bool:
        data = _load()
        pw_hash = data.get("password_hash")
        if not pw_hash:
            return True
        is_rtl = LanguageManager.get_saved_language() != "en"
        for attempt in range(3):
            dlg = PasswordDialog(
                "כניסה לפלאפון כשר חכם" if is_rtl else "Sign in to Smart Kosher Phone",
                (f"הזן ססמה (ניסיון {attempt+1}/3):" if is_rtl
                 else f"Enter password (attempt {attempt+1}/3):"),
                is_rtl)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return False
            if _hash(dlg.password()) == pw_hash:
                return True
            QMessageBox.warning(None, "שגיאה" if is_rtl else "Error",
                                 "ססמה שגויה" if is_rtl else "Incorrect password")
        return False

    @staticmethod
    def get_saved_language() -> str:
        return _load().get("language", "he")
