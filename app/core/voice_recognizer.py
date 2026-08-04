#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoiceRecognizer - זיהוי ספרות קולי לשליחת DTMF
מנסה מודולים אופליין בסדר עדיפות:
  1. vosk  (מהיר, קל, אופליין מלא)
  2. SpeechRecognition + CMU Sphinx (אופליין)
  3. SpeechRecognition + Google (אונליין, fallback)
"""

import re
import threading
import queue
import os
from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal as Signal, QTimer


# מיפוי מילים → ספרה
DIGIT_MAP_HE = {
    # עברית
    "אפס": "0", "אֶפֶס": "0",
    "אחת": "1", "אחד": "1", "אֶחָד": "1",
    "שתיים": "2", "שתים": "2", "שניים": "2", "שְׁנַיִם": "2",
    "שלוש": "3", "שָׁלוֹשׁ": "3",
    "ארבע": "4", "אַרְבַּע": "4",
    "חמש": "5", "חָמֵשׁ": "5",
    "שש": "6", "שֵׁשׁ": "6",
    "שבע": "7", "שֶׁבַע": "7",
    "שמונה": "8", "שְׁמוֹנֶה": "8",
    "תשע": "9", "תֵּשַׁע": "9",
    "כוכבית": "*", "כוכב": "*",
    "סולמית": "#", "סולמת": "#",
}

DIGIT_MAP_EN = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "star": "*", "asterisk": "*", "pound": "#", "hash": "#",
    # digits as spoken
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
    "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
}


def _words_to_digit(text: str) -> Optional[str]:
    """המר טקסט מזוהה לספרה DTMF"""
    text = text.strip().lower()
    # Check Hebrew
    for word, digit in DIGIT_MAP_HE.items():
        if word in text:
            return digit
    # Check English
    for word, digit in DIGIT_MAP_EN.items():
        if word == text or text.startswith(word):
            return digit
    # Single character
    if len(text) == 1 and text in "0123456789*#":
        return text
    return None


class VoiceRecognizer(QObject):
    """
    מנוע זיהוי קול לספרות DTMF
    תומך ב-vosk (אופליין) ו-SpeechRecognition כ-fallback
    """
    digit_recognized  = Signal(str)   # "0"-"9", "*", "#"
    text_recognized   = Signal(str)   # raw text
    listening_started = Signal()
    listening_stopped = Signal()
    error_occurred    = Signal(str)
    status_changed    = Signal(str)

    def __init__(self, parent=None, language_manager=None):
        super().__init__(parent)
        self.lang_mgr = language_manager
        self._listening = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._engine = None          # "vosk" | "sphinx" | "google" | None
        self._vosk_model = None
        self._mic_index: Optional[int] = None
        self._language = "he"        # "he" | "en"
        self._training_phrases: list[str] = []
        self._detect_engine()

    def _t(self, he: str, en: str) -> str:
        if self.lang_mgr is not None and not self.lang_mgr.is_rtl:
            return en
        return he

    # ── Engine detection ──────────────────────────────────

    def _detect_engine(self):
        try:
            import vosk
            self._engine = "vosk"
            self.status_changed.emit(self._t("מנוע זיהוי: Vosk (אופליין)", "Recognition engine: Vosk (offline)"))
            return
        except ImportError:
            pass
        try:
            import speech_recognition as sr
            # Try sphinx
            r = sr.Recognizer()
            with sr.Microphone() as src:
                pass
            self._engine = "sr"
            self.status_changed.emit(self._t("מנוע זיהוי: SpeechRecognition", "Recognition engine: SpeechRecognition"))
            return
        except Exception:
            pass
        self._engine = None
        self.status_changed.emit(self._t("⚠️ לא נמצא מנוע זיהוי — התקן vosk", "⚠️ No recognition engine found — install vosk"))

    # ── Configuration ─────────────────────────────────────

    def set_microphone(self, index: Optional[int]):
        self._mic_index = index

    def set_language(self, lang: str):
        self._language = lang

    def get_available_microphones(self) -> list[tuple[int, str]]:
        """מחזיר רשימת מיקרופונים: [(index, name), ...]"""
        mics = []
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0:
                    mics.append((i, d['name']))
        except Exception:
            try:
                import speech_recognition as sr
                for i, name in enumerate(sr.Microphone.list_microphone_names()):
                    mics.append((i, name))
            except Exception:
                pass
        return mics

    @property
    def engine(self) -> Optional[str]:
        return self._engine

    @property
    def is_listening(self) -> bool:
        return self._listening

    # ── Vosk model management ─────────────────────────────

    def get_vosk_model_path(self) -> str:
        base = os.path.join(os.path.expanduser("~"), "BluePhone", "vosk_models")
        os.makedirs(base, exist_ok=True)
        return base

    def load_vosk_model(self, model_path: str) -> bool:
        try:
            import vosk
            self._vosk_model = vosk.Model(model_path)
            self._engine = "vosk"
            self.status_changed.emit(self._t(f"מודל Vosk נטען: {os.path.basename(model_path)}", f"Vosk model loaded: {os.path.basename(model_path)}"))
            return True
        except Exception as e:
            self.error_occurred.emit(self._t(f"שגיאת טעינת מודל: {e}", f"Model load error: {e}"))
            return False

    def list_vosk_models(self) -> list[str]:
        base = self.get_vosk_model_path()
        return [d for d in os.listdir(base)
                if os.path.isdir(os.path.join(base, d))]

    # ── Listening ─────────────────────────────────────────

    def start_listening(self):
        if self._listening:
            return
        if not self._engine:
            self.error_occurred.emit(
                self._t("לא נמצא מנוע זיהוי. התקן: pip install vosk", "No recognition engine found. Install: pip install vosk"))
            return
        self._listening = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True)
        self._thread.start()
        self.listening_started.emit()
        self.status_changed.emit(self._t("מאזין לפקודות קוליות…", "Listening for voice commands…"))

    def stop_listening(self):
        self._listening = False
        self._stop_event.set()
        self.listening_stopped.emit()
        self.status_changed.emit(self._t("הפסיק להאזין", "Stopped listening"))

    def _listen_loop(self):
        if self._engine == "vosk":
            self._listen_vosk()
        elif self._engine == "sr":
            self._listen_sr()

    def _listen_vosk(self):
        try:
            import vosk
            import sounddevice as sd
            import json

            RATE = 16000
            if not self._vosk_model:
                # Try auto-load
                models = self.list_vosk_models()
                if models:
                    self.load_vosk_model(
                        os.path.join(self.get_vosk_model_path(), models[0]))
                else:
                    self.error_occurred.emit(
                        self._t(
                            f"הורד מודל Vosk לתיקייה:\n{self.get_vosk_model_path()}\nhttps://alphacephei.com/vosk/models",
                            f"Download a Vosk model into:\n{self.get_vosk_model_path()}\nhttps://alphacephei.com/vosk/models"))
                    return

            rec = vosk.KaldiRecognizer(self._vosk_model, RATE)
            # Limit vocabulary to digits for speed + accuracy
            digits_vocab = list(DIGIT_MAP_HE.keys()) + list(DIGIT_MAP_EN.keys())
            rec.SetGrammar(json.dumps(digits_vocab + ["[unk]"]))

            kwargs = {"samplerate": RATE, "channels": 1,
                      "dtype": "int16", "blocksize": 4000}
            if self._mic_index is not None:
                kwargs["device"] = self._mic_index

            with sd.RawInputStream(**kwargs) as stream:
                while self._listening and not self._stop_event.is_set():
                    data, _ = stream.read(4000)
                    if rec.AcceptWaveform(bytes(data)):
                        result = json.loads(rec.Result())
                        text = result.get("text", "").strip()
                        if text:
                            self.text_recognized.emit(text)
                            digit = _words_to_digit(text)
                            if digit:
                                self.digit_recognized.emit(digit)
        except Exception as e:
            self.error_occurred.emit(self._t(f"שגיאת Vosk: {e}", f"Vosk error: {e}"))
            self._listening = False

    def _listen_sr(self):
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            mic_kwargs = {}
            if self._mic_index is not None:
                mic_kwargs["device_index"] = self._mic_index

            with sr.Microphone(**mic_kwargs) as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                while self._listening and not self._stop_event.is_set():
                    try:
                        audio = r.listen(source, timeout=3, phrase_time_limit=3)
                        # Try sphinx (offline)
                        try:
                            text = r.recognize_sphinx(audio,
                                language="he-IL" if self._language == "he" else "en-US")
                        except Exception:
                            # Fallback: Google (online)
                            text = r.recognize_google(audio,
                                language="he-IL" if self._language == "he" else "en-US")
                        text = text.strip().lower()
                        self.text_recognized.emit(text)
                        digit = _words_to_digit(text)
                        if digit:
                            self.digit_recognized.emit(digit)
                    except sr.WaitTimeoutError:
                        continue
                    except Exception:
                        continue
        except Exception as e:
            self.error_occurred.emit(self._t(f"שגיאת SpeechRecognition: {e}", f"SpeechRecognition error: {e}"))
            self._listening = False

    # ── Training ──────────────────────────────────────────

    def record_training_sample(self, digit: str, output_path: str,
                                duration: float = 2.0,
                                callback: Callable = None):
        """הקלט דגימת אימון לספרה"""
        def _rec():
            try:
                import sounddevice as sd
                import wave, numpy as np
                RATE = 16000
                frames = int(RATE * duration)
                data = sd.rec(frames, samplerate=RATE,
                               channels=1, dtype='int16',
                               device=self._mic_index)
                sd.wait()
                with wave.open(output_path, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(RATE)
                    wf.writeframes(data.tobytes())
                if callback:
                    callback(True, output_path)
            except Exception as e:
                if callback:
                    callback(False, str(e))
        threading.Thread(target=_rec, daemon=True).start()
