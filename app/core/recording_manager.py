#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecordingManager - ניהול הקלטות שיחות
תומך בהקלטה אוטומטית, הקלטה לפי מספר/זמן, רשימת הקלטות
"""

import os
import json
import time
import wave
import threading
import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal as Signal, QTimer


@dataclass
class RecordingEntry:
    filename: str
    number: str
    name: str
    direction: str          # incoming / outgoing
    start_time: float
    duration: float = 0.0
    listened: bool = False
    voicemail: bool = False

    @property
    def start_dt(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.start_time)

    @property
    def display_date(self) -> str:
        return self.start_dt.strftime("%d/%m/%Y %H:%M")

    @property
    def display_duration(self) -> str:
        s = int(self.duration)
        return f"{s//60:02d}:{s%60:02d}"


class RecordingManager(QObject):
    """מנהל הקלטות שיחות"""

    recording_started  = Signal(str)   # filename
    recording_stopped  = Signal(str)   # filename
    recording_saved    = Signal(object) # RecordingEntry
    recordings_changed = Signal()

    def __init__(self, base_dir: str = None, parent=None):
        super().__init__(parent)
        self.base_dir = Path(base_dir or os.path.join(
            os.path.expanduser("~"), "BluePhone", "recordings"))
        self.voicemail_dir = Path(os.path.join(
            os.path.expanduser("~"), "BluePhone", "voicemail"))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.voicemail_dir.mkdir(parents=True, exist_ok=True)

        self._index_path = self.base_dir / "index.json"
        self._vm_index_path = self.voicemail_dir / "index.json"
        self._entries: list[RecordingEntry] = []
        self._vm_entries: list[RecordingEntry] = []
        self._load_index()
        self._load_vm_index()

        # Recording state
        self._recording = False
        self._rec_thread: Optional[threading.Thread] = None
        self._rec_file: Optional[str] = None
        self._rec_start: float = 0
        self._stop_event = threading.Event()

        # Settings
        self.auto_record_all   = False
        self.auto_record_numbers: set[str] = set()
        self.auto_record_hours: Optional[tuple[int,int]] = None  # (start_h, end_h)

    # ── Index persistence ────────────────────────────────

    def _load_index(self):
        if self._index_path.exists():
            try:
                data = json.loads(self._index_path.read_text(encoding="utf-8"))
                self._entries = [RecordingEntry(**d) for d in data]
            except Exception:
                self._entries = []

    def _save_index(self):
        try:
            self._index_path.write_text(
                json.dumps([asdict(e) for e in self._entries],
                           ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    def _load_vm_index(self):
        if self._vm_index_path.exists():
            try:
                data = json.loads(self._vm_index_path.read_text(encoding="utf-8"))
                self._vm_entries = [RecordingEntry(**d) for d in data]
            except Exception:
                self._vm_entries = []

    def _save_vm_index(self):
        try:
            self._vm_index_path.write_text(
                json.dumps([asdict(e) for e in self._vm_entries],
                           ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    # ── Recording control ────────────────────────────────

    def should_record(self, number: str) -> bool:
        if self.auto_record_all:
            return True
        if number in self.auto_record_numbers:
            return True
        if self.auto_record_hours:
            h = datetime.datetime.now().hour
            s, e = self.auto_record_hours
            if s <= h < e:
                return True
        return False

    def start_recording(self, number: str, name: str,
                        direction: str, voicemail: bool = False) -> Optional[str]:
        """התחל הקלטה — מחזיר שם קובץ"""
        if self._recording:
            return self._rec_file

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_num = number.replace("+", "").replace(" ", "")
        fname = f"{ts}_{safe_num}.wav"
        out_dir = self.voicemail_dir if voicemail else self.base_dir
        filepath = str(out_dir / fname)

        self._rec_file = filepath
        self._rec_start = time.time()
        self._recording = True
        self._stop_event.clear()
        self._current_meta = (number, name, direction, voicemail)

        self._rec_thread = threading.Thread(
            target=self._record_audio,
            args=(filepath,),
            daemon=True
        )
        self._rec_thread.start()
        self.recording_started.emit(filepath)
        return filepath

    def _record_audio(self, filepath: str):
        """הקלטה דרך sounddevice (אם זמין) או WAV ריק כ-fallback"""
        try:
            import sounddevice as sd
            import numpy as np

            RATE = 16000
            CHANNELS = 1
            frames = []

            def callback(indata, frame_count, time_info, status):
                if not self._stop_event.is_set():
                    frames.append(indata.copy())

            with sd.InputStream(samplerate=RATE, channels=CHANNELS,
                                dtype='int16', callback=callback):
                self._stop_event.wait()

            # Save WAV
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(RATE)
                if frames:
                    import numpy as np
                    wf.writeframes(np.concatenate(frames).tobytes())

        except ImportError:
            # sounddevice not available — create placeholder WAV
            self._stop_event.wait()
            try:
                with wave.open(filepath, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(b'\x00' * 32000)
            except Exception:
                pass
        except Exception:
            self._stop_event.wait()

    def stop_recording(self) -> Optional[RecordingEntry]:
        if not self._recording:
            return None
        self._recording = False
        self._stop_event.set()

        duration = time.time() - self._rec_start
        number, name, direction, voicemail = self._current_meta
        fname = os.path.basename(self._rec_file)

        entry = RecordingEntry(
            filename=fname,
            number=number,
            name=name,
            direction=direction,
            start_time=self._rec_start,
            duration=duration,
            listened=False,
            voicemail=voicemail
        )

        if voicemail:
            self._vm_entries.insert(0, entry)
            self._save_vm_index()
        else:
            self._entries.insert(0, entry)
            self._save_index()

        self.recording_stopped.emit(self._rec_file)
        self.recording_saved.emit(entry)
        self.recordings_changed.emit()
        self._rec_file = None
        return entry

    # ── Entries ──────────────────────────────────────────

    def get_recordings(self) -> list:
        return list(self._entries)

    def get_voicemails(self) -> list:
        return list(self._vm_entries)

    def mark_listened(self, filename: str, voicemail: bool = False):
        lst = self._vm_entries if voicemail else self._entries
        for e in lst:
            if e.filename == filename:
                e.listened = True
        if voicemail:
            self._save_vm_index()
        else:
            self._save_index()
        self.recordings_changed.emit()

    def delete_recording(self, filename: str, voicemail: bool = False):
        lst = self._vm_entries if voicemail else self._entries
        out_dir = self.voicemail_dir if voicemail else self.base_dir
        filepath = out_dir / filename
        try:
            if filepath.exists():
                filepath.unlink()
        except Exception:
            pass
        if voicemail:
            self._vm_entries = [e for e in self._vm_entries
                                 if e.filename != filename]
            self._save_vm_index()
        else:
            self._entries = [e for e in self._entries
                             if e.filename != filename]
            self._save_index()
        self.recordings_changed.emit()

    def get_recording_path(self, filename: str, voicemail: bool = False) -> str:
        d = self.voicemail_dir if voicemail else self.base_dir
        return str(d / filename)

    @property
    def is_recording(self) -> bool:
        return self._recording

    def unread_voicemail_count(self) -> int:
        return sum(1 for e in self._vm_entries if not e.listened)
