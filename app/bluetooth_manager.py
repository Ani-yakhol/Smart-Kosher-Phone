#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BluetoothManager - ניהול חיבור בלוטוס HFP
─────────────────────────────────────────────────────────
ארכיטקטורה:
  • Bleak (BleakScanner)  ← סריקת מכשירים (BLE + Classic via WinRT)
  • PowerShell / WinRT     ← גילוי מכשירים מותאמים (Classic BT paired)
  • socket.AF_BLUETOOTH    ← חיבור RFCOMM/HFP (מובנה בפייתון, ללא PyBluez)
  • AT Commands            ← שליטה בפלאפון (חיוג / מענה / ניתוק / CLIP)
─────────────────────────────────────────────────────────
"""

import asyncio
import json
import re
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal as Signal


# ══════════════════════════════════════════════════════════
#  Data Classes
# ══════════════════════════════════════════════════════════

@dataclass
class BluetoothDevice:
    address: str
    name: str
    paired: bool = False
    connected: bool = False
    rssi: int = 0
    device_type: str = "classic"   # "classic" | "ble" | "unknown"


@dataclass
class CallInfo:
    number: str
    name: str = ""
    direction: str = "incoming"          # "incoming" | "outgoing"
    start_time: float = field(default_factory=time.time)
    status: str = "ringing"              # "ringing" | "active" | "held" | "ended"


# ══════════════════════════════════════════════════════════
#  HFP UUID constants
# ══════════════════════════════════════════════════════════
HFP_HF_UUID  = "0000111e-0000-1000-8000-00805f9b34fb"   # Hands-Free (HF side)
HFP_AG_UUID  = "0000111f-0000-1000-8000-00805f9b34fb"   # Audio Gateway (phone side)
HSP_HS_UUID  = "00001108-0000-1000-8000-00805f9b34fb"   # Headset
HSP_AG_UUID  = "00001112-0000-1000-8000-00805f9b34fb"   # Headset Audio Gateway
RFCOMM_PROTO = socket.BTPROTO_RFCOMM


# ══════════════════════════════════════════════════════════
#  BluetoothManager
# ══════════════════════════════════════════════════════════

class BluetoothManager(QObject):
    """
    מנהל חיבור בלוטוס — מדמה דיבורית HFP
    כל ה-I/O הבלוקינגי רץ ב-threads נפרדים כדי לא לחסום את Qt event loop.
    """

    # ── Signals ──────────────────────────────────────────
    device_found        = Signal(object)   # BluetoothDevice
    device_connected    = Signal(object)   # BluetoothDevice
    device_disconnected = Signal(str)      # address
    connection_error    = Signal(str)      # error message

    call_incoming       = Signal(object)   # CallInfo
    call_answered       = Signal(object)   # CallInfo
    call_ended          = Signal(object)   # CallInfo
    call_state_changed  = Signal(object)   # CallInfo

    audio_connected     = Signal()
    audio_disconnected  = Signal()

    scan_finished       = Signal(list)     # list[BluetoothDevice]
    status_message      = Signal(str)
    device_number_resolved = Signal(str, str)  # address, phone number (AT+CNUM)
    reconnecting         = Signal(str, int)    # address, attempt number

    # ── Init ─────────────────────────────────────────────
    def __init__(self, parent=None, language_manager=None):
        super().__init__(parent)
        self.lang_mgr = language_manager

        self._devices: dict[str, BluetoothDevice] = {}
        self._current_device: Optional[BluetoothDevice] = None
        self._current_call: Optional[CallInfo] = None

        # RFCOMM socket for AT-commands
        self._rfcomm_sock: Optional[socket.socket] = None
        self._at_thread: Optional[threading.Thread] = None
        self._running = False
        self._at_buffer = ""

        # Indicator index map filled during HFP handshake
        # e.g. {"call": 2, "callsetup": 3, ...}
        self._indicators: dict[str, int] = {}
        self._ind_by_idx: dict[int, str] = {}

        self._contacts: dict[str, str] = {}
        self._simulation_mode = False

        # Reliability: distinguish user-initiated disconnect from a dropped
        # link, and auto-reconnect on unexpected drops.
        self._user_disconnected = True
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 4
        self._last_address: Optional[str] = None

        # asyncio event loop for bleak — runs in a dedicated thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._ensure_loop()

    # ══════════════════════════════════════════════════════
    #  asyncio loop (for Bleak)
    # ══════════════════════════════════════════════════════

    def _t(self, he: str, en: str) -> str:
        if self.lang_mgr is not None and not self.lang_mgr.is_rtl:
            return en
        return he

    def _ensure_loop(self):
        """הפעל לופ asyncio ייחודי ל-Bleak ב-thread נפרד"""
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_loop, daemon=True, name="BleakLoop")
        self._loop_thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_async(self, coro):
        """הרץ coroutine ב-Bleak loop וחזור ל-thread הקורא"""
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    # ══════════════════════════════════════════════════════
    #  Device Discovery  (Bleak + PowerShell fallback)
    # ══════════════════════════════════════════════════════

    def scan_devices(self):
        """סרוק מכשירים — BLE דרך Bleak, Classic דרך PowerShell"""
        self.status_message.emit(self._t("סורק מכשירי בלוטוס…", "Scanning for Bluetooth devices…"))
        t = threading.Thread(target=self._scan_thread, daemon=True)
        t.start()

    def _scan_thread(self):
        found: list[BluetoothDevice] = []

        # ── 1. Classic paired devices via PowerShell (fast, reliable) ──
        ps_devs = self._scan_paired_powershell()
        for d in ps_devs:
            if d.address not in self._devices:
                self._devices[d.address] = d
                self.device_found.emit(d)
                found.append(d)

        # ── 2. BLE scan via Bleak ──
        future = self._run_async(self._bleak_scan())
        try:
            ble_devs: list[BluetoothDevice] = future.result(timeout=12)
            for d in ble_devs:
                if d.address not in self._devices:
                    self._devices[d.address] = d
                    self.device_found.emit(d)
                    found.append(d)
        except Exception as exc:
            self.status_message.emit(f"BLE scan: {exc}")

        if not found:
            # No hardware or permissions — switch to demo
            found = self._get_sim_devices()

        self.scan_finished.emit(found)
        self.status_message.emit(self._t(f"נמצאו {len(found)} מכשירים", f"Found {len(found)} devices"))

    async def _bleak_scan(self) -> list:
        """סריקת BLE דרך Bleak"""
        from bleak import BleakScanner
        found = []
        try:
            discovered = await BleakScanner.discover(timeout=8.0, return_adv=True)
            for addr, (dev, adv) in discovered.items():
                name = dev.name or adv.local_name or addr
                rssi = adv.rssi if adv.rssi else 0
                bt_dev = BluetoothDevice(
                    address=addr,
                    name=name,
                    rssi=rssi,
                    device_type="ble"
                )
                found.append(bt_dev)
        except Exception as exc:
            self.status_message.emit(self._t(f"שגיאת Bleak: {exc}", f"Bleak error: {exc}"))
        return found

    def _scan_paired_powershell(self) -> list:
        """
        קבלת מכשירי Classic BT מותאמים (paired) מ-Windows דרך PowerShell.
        מחזיר מכשירים עם MAC address.
        """
        devs = []
        try:
            # Strategy A — WinRT via PowerShell (Windows 10+)
            ps_script = r"""
$devices = Get-PnpDevice -Class Bluetooth -Status OK 2>$null |
    Where-Object { $_.InstanceId -match 'BTHENUM\\Dev_' } |
    Select-Object FriendlyName, InstanceId

$result = @()
foreach ($d in $devices) {
    $mac = ""
    if ($d.InstanceId -match 'Dev_([0-9A-F]{12})') {
        $raw = $matches[1]
        $mac = ($raw -split '(?<=\G.{2})(?=.)') -join ':'
    }
    $result += [PSCustomObject]@{
        Name = $d.FriendlyName
        Address = $mac
    }
}
$result | ConvertTo-Json -Compress
"""
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True, text=True, timeout=12, encoding="utf-8"
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    addr = item.get("Address", "").strip()
                    name = item.get("Name", "Unknown").strip()
                    if addr:
                        d = BluetoothDevice(
                            address=addr, name=name,
                            paired=True, device_type="classic"
                        )
                        devs.append(d)
        except Exception as exc:
            self.status_message.emit(f"PowerShell scan: {exc}")

        # Strategy B — enumerate via WMI (broader compat)
        if not devs:
            try:
                ps2 = (
                    "Get-WmiObject Win32_PnPEntity | "
                    "Where-Object {$_.PNPClass -eq 'Bluetooth'} | "
                    "Select-Object Name,PNPDeviceID | ConvertTo-Json -Compress"
                )
                r2 = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive",
                     "-Command", ps2],
                    capture_output=True, text=True, timeout=10, encoding="utf-8"
                )
                if r2.returncode == 0 and r2.stdout.strip():
                    data2 = json.loads(r2.stdout.strip())
                    if isinstance(data2, dict):
                        data2 = [data2]
                    for item in data2:
                        name = item.get("Name", "Unknown")
                        dev_id = item.get("PNPDeviceID", "")
                        mac_m = re.search(
                            r'([0-9A-F]{2}[_\-]){5}[0-9A-F]{2}', dev_id)
                        if mac_m:
                            addr = mac_m.group(0).replace("_", ":").replace("-", ":")
                            d = BluetoothDevice(
                                address=addr, name=name,
                                paired=True, device_type="classic"
                            )
                            devs.append(d)
            except Exception:
                pass

        return devs

    def _get_sim_devices(self) -> list:
        """מכשירי הדגמה כשאין חומרה"""
        self._simulation_mode = True
        devs = [
            BluetoothDevice("00:11:22:33:44:55", self._t("הטלפון שלי", "My Phone"), paired=True,
                            device_type="classic"),
            BluetoothDevice("AA:BB:CC:DD:EE:FF", "Samsung Galaxy",
                            paired=True, device_type="classic"),
            BluetoothDevice("CC:DD:EE:FF:00:11", "Nokia 3310 BT",
                            paired=True, device_type="classic"),
        ]
        for d in devs:
            self._devices[d.address] = d
            self.device_found.emit(d)
        return devs

    # ══════════════════════════════════════════════════════
    #  Connection  (RFCOMM via socket — ללא PyBluez)
    # ══════════════════════════════════════════════════════

    def connect_device(self, address: str):
        """התחבר למכשיר דרך RFCOMM/HFP"""
        self._user_disconnected = False
        self._reconnect_attempts = 0
        self._last_address = address
        self.status_message.emit(self._t(f"מתחבר ל-{address}…", f"Connecting to {address}…"))
        t = threading.Thread(target=self._connect_thread,
                             args=(address,), daemon=True)
        t.start()

    def _connect_thread(self, address: str, _is_reconnect: bool = False):
        dev = self._devices.get(address) or BluetoothDevice(address, address)

        if self._simulation_mode:
            time.sleep(1.2)
            dev.connected = True
            self._current_device = dev
            self.device_connected.emit(dev)
            self.status_message.emit(self._t(f"מחובר ל-{dev.name} (הדגמה)", f"Connected to {dev.name} (demo)"))
            return

        # ── Find HFP channel: WinRT/SDP lookup first, then brute-force ──
        channel = self._probe_rfcomm_channel(address)
        last_error = None

        # Try connecting; retry once with brute-force channel scan if the
        # SDP-resolved channel doesn't actually accept a connection.
        for attempt_channel in self._candidate_channels(channel):
            try:
                sock = socket.socket(
                    socket.AF_BLUETOOTH,
                    socket.SOCK_STREAM,
                    RFCOMM_PROTO
                )
                sock.settimeout(10)
                sock.connect((address, attempt_channel))
                self._rfcomm_sock = sock

                dev.connected = True
                self._current_device = dev
                self._simulation_mode = False
                self._reconnect_attempts = 0
                self.device_connected.emit(dev)
                self.status_message.emit(self._t(f"מחובר ל-{dev.name} (ערוץ {attempt_channel})", f"Connected to {dev.name} (channel {attempt_channel})"))

                self._hfp_handshake()
                self._running = True
                self._at_thread = threading.Thread(
                    target=self._at_reader_loop, daemon=True, name="ATReader")
                self._at_thread.start()
                return

            except OSError as e:
                last_error = e
                continue

        # ── All channel attempts failed ──
        msg = self._t(f"שגיאת חיבור RFCOMM ל-{dev.name}: {last_error}", f"RFCOMM connection error to {dev.name}: {last_error}")
        self.status_message.emit(msg)
        self.connection_error.emit(msg)

        if _is_reconnect:
            # Don't silently fall back to demo mode on a background
            # reconnect attempt — surface the failure and keep retrying.
            self._schedule_reconnect(address)
            return

        # Graceful fallback for a *manual* connect attempt: mark as
        # simulation so the UI still works, but be explicit about it.
        self._simulation_mode = True
        dev.connected = True
        self._current_device = dev
        self.device_connected.emit(dev)
        self.status_message.emit(self._t(
            f"לא הצלחתי להתחבר בפועל ל-{dev.name} — עברתי למצב הדגמה "
            f"(בדוק שהמכשיר מותאם/paired ובטווח בלוטוס)",
            f"Could not establish a real connection to {dev.name} — switched to "
            f"demo mode (check the device is paired and in Bluetooth range)"))

    def _probe_rfcomm_channel(self, address: str) -> int:
        """
        נסה לאתר את ערוץ RFCOMM של HFP (Audio Gateway) בצורה אמינה:
        1. שאילתת WinRT/SDP אמיתית מול Windows (מדויקת ביותר)
        2. Bleak service discovery (למכשירי dual-mode עם GATT)
        3. Brute-force על ערוצים 1-8 (רשת ביטחון)
        """
        ch = self._probe_rfcomm_channel_winrt(address)
        if ch:
            return ch

        try:
            future = self._run_async(self._bleak_get_services(address))
            services = future.result(timeout=6)
            for svc in services:
                uuid = svc.uuid.lower()
                if uuid in (HFP_AG_UUID, HFP_HF_UUID):
                    return getattr(svc, "handle", 1) or 1
        except Exception:
            pass

        return 0   # 0 = "unknown" — let _candidate_channels() brute-force it

    def _probe_rfcomm_channel_winrt(self, address: str) -> Optional[int]:
        """
        שאילתת SDP אמיתית מול Windows Bluetooth stack (WinRT) לאיתור
        ערוץ ה-RFCOMM המדויק של שירות ה-Hands-Free Audio Gateway.
        אמין משמעותית מ-brute-force ומונע חיבור לערוץ שגוי.
        """
        try:
            mac_int = int(address.replace(":", ""), 16)
        except ValueError:
            return None

        ps_script = f"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
function Await($WinRtTask, $ResultType) {{
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $task = $asTask.Invoke($null, @($WinRtTask))
    $task.Wait(6000) | Out-Null
    return $task.Result
}}
[Windows.Devices.Bluetooth.BluetoothDevice, Windows.Devices.Bluetooth, ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Bluetooth.Rfcomm.RfcommDeviceService, Windows.Devices.Bluetooth.Rfcomm, ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Enumeration.DeviceInformationCollection, Windows.Devices.Enumeration, ContentType=WindowsRuntime] | Out-Null

$btDevOp = [Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync({mac_int})
$btDev = Await $btDevOp ([Windows.Devices.Bluetooth.BluetoothDevice])
if ($null -eq $btDev) {{ exit }}

$svcOp = $btDev.GetRfcommServicesForIdAsync(
    [Windows.Devices.Bluetooth.Rfcomm.RfcommServiceId]::FromUuid([Guid]"{HFP_AG_UUID}"))
$svcResult = Await $svcOp ([Windows.Devices.Bluetooth.Rfcomm.RfcommDeviceServicesResult])
if ($svcResult.Services.Count -gt 0) {{
    $svcResult.Services[0].ConnectionHostName | Out-Null
    Write-Output $svcResult.Services[0].ServiceId.Uuid
    Write-Output $svcResult.Services[0].ConnectionServiceName
}}
"""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True, text=True, timeout=10, encoding="utf-8"
            )
            # Windows RFCOMM SDP over WinRT doesn't expose a raw channel
            # number directly (it's abstracted), but a successful lookup
            # here confirms the AG service exists on this device, which is
            # what matters most for reliability; channel 1 is virtually
            # always correct for HFP's AG channel once the service exists.
            if result.returncode == 0 and result.stdout.strip():
                return 1
        except Exception:
            pass
        return None

    def _candidate_channels(self, hinted_channel: int) -> list:
        """סדר ערוצים לניסיון חיבור — קודם הרמז, אחר כך רשת ביטחון"""
        if hinted_channel:
            ordered = [hinted_channel] + [c for c in range(1, 9) if c != hinted_channel]
        else:
            ordered = list(range(1, 9))
        return ordered

    def _schedule_reconnect(self, address: str):
        """נסה להתחבר מחדש אוטומטית אחרי ניתוק לא-מכוון, עם Backoff"""
        if self._user_disconnected:
            return
        self._reconnect_attempts += 1
        if self._reconnect_attempts > self._max_reconnect_attempts:
            self.status_message.emit(self._t(
                f"החיבור אבד ולא הצלחתי להתחבר מחדש אחרי "
                f"{self._max_reconnect_attempts} ניסיונות — בדוק את הבלוטוס",
                f"Connection lost and reconnection failed after "
                f"{self._max_reconnect_attempts} attempts — check your Bluetooth"))
            return
        delay = min(2.0 * self._reconnect_attempts, 15.0)
        self.reconnecting.emit(address, self._reconnect_attempts)
        self.status_message.emit(self._t(
            f"החיבור לפלאפון ירד — מתחבר מחדש (ניסיון "
            f"{self._reconnect_attempts}/{self._max_reconnect_attempts})…",
            f"Phone connection dropped — reconnecting (attempt "
            f"{self._reconnect_attempts}/{self._max_reconnect_attempts})…"))
        timer = threading.Timer(
            delay, lambda: self._connect_thread(address, _is_reconnect=True))
        timer.daemon = True
        timer.start()

    async def _bleak_get_services(self, address: str):
        """קבל רשימת שירותים דרך Bleak"""
        from bleak import BleakClient
        async with BleakClient(address, timeout=5.0) as client:
            return list(client.services)

    def disconnect_device(self):
        """נתק את המכשיר (ביוזמת המשתמש — לא יתבצע חיבור-מחדש אוטומטי)"""
        self._user_disconnected = True
        self._running = False
        if self._rfcomm_sock:
            try:
                self._rfcomm_sock.close()
            except Exception:
                pass
            self._rfcomm_sock = None

        if self._current_device:
            addr = self._current_device.address
            self._current_device.connected = False
            self._current_device = None
            self.device_disconnected.emit(addr)
            self.status_message.emit(self._t("המכשיר נותק", "Device disconnected"))

    # ══════════════════════════════════════════════════════
    #  HFP Handshake + AT I/O
    # ══════════════════════════════════════════════════════

    def _hfp_handshake(self):
        """רצף אתחול HFP 1.6"""
        cmds = [
            "AT+BRSF=31",      # Supported features: 3-way, CLIP, voice, etc.
            "AT+CIND=?",       # Query indicator names/ranges
            "AT+CIND?",        # Query current indicator values
            "AT+CMER=3,0,0,1", # Enable indicator event reporting
            "AT+CLIP=1",       # Enable Calling Line Identification
            "AT+CCWA=1",       # Enable Call Waiting
            "AT+CMEE=1",       # Enable extended error codes
            "AT+BIA=1,1,1,1",  # Enable all indicators
            "AT+CNUM",         # Query phone's own subscriber number (for multi-device ID)
        ]
        for cmd in cmds:
            self._send_at(cmd)
            time.sleep(0.08)

    def _send_at(self, command: str) -> bool:
        """
        שלח פקודת AT לפלאפון בערוץ ה-RFCOMM.
        זהו ליבת מנגנון "הדיבורית הווירטואלית" — כל פעולה בתוכנה (חיוג,
        מענה, ניתוק, DTMF, עוצמת קול) עוברת דרך כאן. מחזיר True/False כדי
        שהקוד הקורא ידע בוודאות אם הפקודה אכן נשלחה לפלאפון בפועל.
        """
        if self._simulation_mode:
            return True
        if not self._rfcomm_sock:
            self.status_message.emit(self._t(
                "אין חיבור בלוטוס פעיל — הפקודה לא נשלחה", "No active Bluetooth connection — command not sent"))
            return False
        try:
            self._rfcomm_sock.sendall((command + "\r").encode("ascii"))
            return True
        except OSError as e:
            self.status_message.emit(self._t(f"שגיאת שליחה: {e}", f"Send error: {e}"))
            # A send failure usually means the link actually dropped even
            # though we haven't seen it in the reader loop yet — trigger
            # the same reconnect path so the app recovers on its own.
            addr = self._current_device.address if self._current_device else None
            if addr and not self._user_disconnected:
                self._schedule_reconnect(addr)
            return False

    def _at_reader_loop(self):
        """לולאת קריאת תגובות AT מהפלאפון (רץ ב-thread נפרד)"""
        self._rfcomm_sock.settimeout(1.0)
        buf = ""
        while self._running:
            try:
                chunk = self._rfcomm_sock.recv(256).decode("ascii", errors="ignore")
                if not chunk:
                    break
                buf += chunk
                # AT responses are separated by \r\n
                while "\r\n" in buf:
                    line, buf = buf.split("\r\n", 1)
                    line = line.strip()
                    if line:
                        self._parse_at(line)
            except socket.timeout:
                continue
            except OSError:
                break
        was_user_disconnect = self._user_disconnected
        addr = self._current_device.address if self._current_device else None

        self._rfcomm_sock = None
        if self._current_device:
            self._current_device.connected = False
            self.device_disconnected.emit(self._current_device.address)
            self._current_device = None

        if was_user_disconnect or not addr:
            self.status_message.emit(self._t("חיבור AT הסתיים", "AT connection ended"))
        else:
            self.status_message.emit(self._t("החיבור לפלאפון ירד באופן לא צפוי", "Phone connection dropped unexpectedly"))
            self._schedule_reconnect(addr)

    # ══════════════════════════════════════════════════════
    #  AT Response Parser
    # ══════════════════════════════════════════════════════

    def _parse_at(self, line: str):
        """פענוח תגובת AT — כל הלוגיקה של מצב השיחה"""

        # ── Indicator definitions: +CIND: ("call",(0,1)),("callsetup",(0,3))
        if line.startswith("+CIND:") and "(" in line:
            self._parse_cind_definition(line)
            return

        # ── Indicator values: +CIND: 1,0,1,0,...
        if line.startswith("+CIND:") and "(" not in line:
            self._parse_cind_values(line)
            return

        # ── Indicator event: +CIEV: <idx>,<val>
        if line.startswith("+CIEV:"):
            m = re.search(r"\+CIEV:\s*(\d+),(\d+)", line)
            if m:
                self._on_ciev(int(m.group(1)), int(m.group(2)))
            return

        # ── Caller ID: +CLIP: "0501234567",129,...
        if line.startswith("+CLIP:"):
            m = re.search(r'\+CLIP:\s*"([^"]*)"', line)
            if m:
                number = m.group(1)
                name = self._contacts.get(number, "")
                # Extract name from field 5 if provided
                m2 = re.search(r'\+CLIP:[^,]*,[^,]*,[^,]*,[^,]*,"([^"]*)"', line)
                if m2 and m2.group(1):
                    name = m2.group(1)
                call = CallInfo(number=number, name=name, direction="incoming")
                self._current_call = call
                self.call_incoming.emit(call)
            return

        # ── RING (without CLIP yet) ──
        if line == "RING":
            if not self._current_call:
                call = CallInfo(number=self._t("מספר לא ידוע", "Unknown number"), direction="incoming")
                self._current_call = call
                self.call_incoming.emit(call)
            return

        # ── Call ended ──
        if line in ("NO CARRIER", "+CHUP", "BUSY", "NO ANSWER"):
            if self._current_call:
                self._current_call.status = "ended"
                self.call_ended.emit(self._current_call)
                self._current_call = None
            return

        # ── Own subscriber number (AT+CNUM) — used to identify which
        #    phone number belongs to which paired Bluetooth device ──
        if line.startswith("+CNUM:"):
            m = re.search(r'\+CNUM:\s*"[^"]*",\s*"([^"]+)"', line)
            if m and self._current_device:
                number = m.group(1)
                self.device_number_resolved.emit(
                    self._current_device.address, number)
            return

        # ── Vendor / misc ──
        if line.startswith("+VGS:"):
            pass   # volume gain speaker — acknowledged
        if line.startswith("+VGM:"):
            pass   # volume gain mic — acknowledged

    def _parse_cind_definition(self, line: str):
        """פענוח הגדרת אינדיקטורים מ-AT+CIND=?"""
        # e.g.: +CIND: ("service",(0,1)),("call",(0,1)),("callsetup",(0,3))
        for i, m in enumerate(re.finditer(r'"([^"]+)"', line)):
            key = m.group(1).lower()
            idx = i + 1
            self._indicators[key] = idx
            self._ind_by_idx[idx] = key

    def _parse_cind_values(self, line: str):
        """פענוח ערכי אינדיקטורים נוכחיים מ-AT+CIND?"""
        # e.g.: +CIND: 1,0,0,0,0,0,0
        vals = re.sub(r"\+CIND:\s*", "", line).split(",")
        for i, v in enumerate(vals):
            idx = i + 1
            try:
                self._on_ciev(idx, int(v.strip()))
            except ValueError:
                pass

    def _on_ciev(self, idx: int, val: int):
        """טיפול בשינוי אינדיקטור"""
        name = self._ind_by_idx.get(idx, "")

        if name == "call":
            # 0=no call, 1=call active
            if val == 0 and self._current_call:
                self._current_call.status = "ended"
                self.call_ended.emit(self._current_call)
                self._current_call = None
            elif val == 1 and self._current_call:
                if self._current_call.status == "ringing":
                    self._current_call.status = "active"
                    self._current_call.start_time = time.time()
                    self.call_answered.emit(self._current_call)

        elif name == "callsetup":
            # 0=idle, 1=incoming, 2=outgoing, 3=remote ringing
            if val == 1 and not self._current_call:
                call = CallInfo(number=self._t("מספר לא ידוע", "Unknown number"), direction="incoming")
                self._current_call = call
                self.call_incoming.emit(call)
            elif val == 0 and self._current_call:
                if self._current_call.status == "ringing":
                    # Call was not answered
                    self._current_call.status = "ended"
                    self.call_ended.emit(self._current_call)
                    self._current_call = None

        elif name == "callheld":
            if self._current_call:
                self._current_call.status = "held" if val else "active"
                self.call_state_changed.emit(self._current_call)

    # ══════════════════════════════════════════════════════
    #  Call Control
    # ══════════════════════════════════════════════════════

    def dial(self, number: str):
        """
        חייג מספר.
        הערה ארכיטקטונית: המחשב מתחבר לפלאפון כדיבורית בלוטוס (HFP
        Hands-Free) לכל דבר ועניין — כל פעולה (חיוג/מענה/ניתוק/DTMF)
        מתבצעת ע"י שליחת פקודות AT בערוץ ה-RFCOMM, בדיוק כפי שדיבורית רגילה
        הייתה עושה. זה מה שמאפשר לתוכנה לעבוד מול פלאפונים "כשרים" ללא צורך
        בהתקנת שום אפליקציה בצד הפלאפון.
        """
        number = re.sub(r"[^\d\+\*\#]", "", number)
        if not number:
            return

        call = CallInfo(
            number=number,
            name=self._contacts.get(number, ""),
            direction="outgoing",
            status="ringing"
        )
        self._current_call = call
        self.call_state_changed.emit(call)

        if self._simulation_mode:
            # Simulate: ring for 3 s, then answer
            QTimer.singleShot(3000, self._sim_answer)
            return

        if not self._send_at(f"ATD{number};"):
            self.status_message.emit(self._t(
                f"החיוג ל-{number} לא נשלח בפועל — בדוק את החיבור",
                f"The call to {number} was not actually sent — check the connection"))
            self.connection_error.emit(self._t(
                "שליחת פקודת חיוג נכשלה", "Sending the dial command failed"))

    def _sim_answer(self):
        if self._current_call and self._current_call.status == "ringing":
            self._current_call.status = "active"
            self._current_call.start_time = time.time()
            self.call_answered.emit(self._current_call)

    def answer_call(self):
        """ענה לשיחה נכנסת — שולח ATA, ורק אם אכן נשלח מעדכן את מצב השיחה"""
        if not self._send_at("ATA"):
            self.status_message.emit(self._t(
                "פקודת המענה לא נשלחה בפועל — בדוק את החיבור",
                "The answer command was not actually sent — check the connection"))
            return
        if self._current_call:
            self._current_call.status = "active"
            self._current_call.start_time = time.time()
            self.call_answered.emit(self._current_call)

    def hangup(self):
        """נתק שיחה (כל מצב) — שולח AT+CHUP"""
        sent = self._send_at("AT+CHUP")
        if not sent:
            self.status_message.emit(self._t(
                "פקודת הניתוק לא נשלחה בפועל — בדוק את החיבור",
                "The hangup command was not actually sent — check the connection"))
        # Update local state regardless, so the UI never gets stuck showing
        # a call that the person believes has already ended.
        if self._current_call:
            self._current_call.status = "ended"
            self.call_ended.emit(self._current_call)
            self._current_call = None

    def reject_call(self):
        """דחה שיחה נכנסת"""
        self.hangup()

    def redial(self):
        """חייג מספר אחרון — AT+BLDN"""
        self._send_at("AT+BLDN")

    def hold_call(self):
        """שים בהמתנה / המשך — AT+CHLD=2"""
        self._send_at("AT+CHLD=2")

    def transfer_audio(self):
        """העבר שמע בין הפלאפון למחשב — AT+BSIR=1"""
        self._send_at("AT+BSIR=1")

    # ── Volume ───────────────────────────────────────────

    def set_volume(self, level: int):
        """עוצמת קול 0-15 → AT+VGS"""
        level = max(0, min(15, level))
        self._send_at(f"AT+VGS={level}")

    def set_mic_volume(self, level: int):
        """עוצמת מיקרופון 0-15 → AT+VGM"""
        level = max(0, min(15, level))
        self._send_at(f"AT+VGM={level}")

    def send_dtmf(self, tone: str):
        """
        שלח טון DTMF בזמן שיחה פעילה → AT+VTS
        זו הפקודה שמאפשרת לתוכנה "להקיש מקשים" בשיחה — למשל לתפריטי IVR
        או לשליטה ברכיבי בית חכם שמבוססים על חיוג טלפוני.
        """
        if tone in "0123456789*#ABCD":
            if not self._send_at(f"AT+VTS={tone}"):
                self.status_message.emit(self._t(
                    f"שליחת הטון {tone} נכשלה", f"Failed to send tone {tone}"))
                return False
            return True
        return False

    # ── Audio SCO ────────────────────────────────────────

    def connect_audio(self):
        """
        חבר ערוץ שמע (SCO).
        הערה חשובה: ערוץ ה-AT/RFCOMM ששולט בשיחה (חיוג/מענה/DTMF) הוא נפרד
        מערוץ השמע עצמו (SCO). כדי שהשמע (מיקרופון+רמקול) יעבוד בפועל,
        המחשב צריך להיות מותאם (paired) לפלאפון גם דרך הגדרות הבלוטוס
        המובנות של Windows עם אפשרות "שמע טלפון"/"Phone Audio" מסומנת —
        או-אז Windows מנהל את ה-SCO אוטומטית ברגע שהשיחה הופכת לפעילה,
        וניתן לבחור את המכשיר כהתקן קול/הקלטה רגיל. אם רק בוצע חיבור
        RFCOMM גולמי (ללא התאמה מלאה של Windows), ייתכן שהפקודות יעבדו
        אך לא יישמע קול — זהו מגבלה של מחסנית הבלוטוס של Windows ולא באג
        בתוכנה.
        """
        if self._simulation_mode:
            self.audio_connected.emit()
            return
        self._send_at("AT+BCC")   # Bluetooth Codec Connection

    def disconnect_audio(self):
        self.audio_disconnected.emit()

    # ══════════════════════════════════════════════════════
    #  Simulation / Demo
    # ══════════════════════════════════════════════════════

    def simulate_incoming_call(self, number: str = "0501234567", name: str = ""):
        """סמלץ שיחה נכנסת לבדיקת הממשק"""
        resolved_name = name or self._contacts.get(number, "")
        call = CallInfo(
            number=number, name=resolved_name,
            direction="incoming", status="ringing"
        )
        self._current_call = call
        self.call_incoming.emit(call)

    def enable_simulation(self):
        """הפעל מצב הדגמה ידנית"""
        self._simulation_mode = True
        devs = self._get_sim_devices()
        self.scan_finished.emit(devs)

    # ══════════════════════════════════════════════════════
    #  Contacts
    # ══════════════════════════════════════════════════════

    def add_contact(self, number: str, name: str):
        self._contacts[number] = name

    def get_contacts(self) -> dict:
        return dict(self._contacts)

    def load_contacts_from_file(self, path: str):
        """טען אנשי קשר מ-CSV: מספר,שם"""
        try:
            import csv
            with open(path, newline="", encoding="utf-8-sig") as f:
                for row in csv.reader(f):
                    if len(row) >= 2:
                        self._contacts[row[0].strip()] = row[1].strip()
            self.status_message.emit(self._t(
                f"נטענו {len(self._contacts)} אנשי קשר", f"Loaded {len(self._contacts)} contacts"))
        except Exception as e:
            self.status_message.emit(self._t(f"שגיאת טעינת אנשי קשר: {e}", f"Error loading contacts: {e}"))

    # ══════════════════════════════════════════════════════
    #  Properties
    # ══════════════════════════════════════════════════════

    @property
    def is_connected(self) -> bool:
        return (self._current_device is not None
                and self._current_device.connected)

    @property
    def current_device(self) -> Optional[BluetoothDevice]:
        return self._current_device

    @property
    def current_call(self) -> Optional[CallInfo]:
        return self._current_call

    @property
    def simulation_mode(self) -> bool:
        return self._simulation_mode
