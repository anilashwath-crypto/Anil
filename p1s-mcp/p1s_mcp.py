#!/usr/bin/env python3
"""Bambu Lab P1S connector for Claude (MCP server).

Talks to the printer in LAN mode:
  * MQTT over TLS  :8883  (user "bblp", password = LAN access code) - status + control
  * FTPS (implicit):990   - upload .3mf / .gcode.3mf files to the printer
  * Camera stream  :6000  - JPEG snapshot (P1 series)

Config (environment variables):
  P1S_HOST          printer IP address
  P1S_SERIAL        printer serial number (Settings > Device on the printer)
  P1S_ACCESS_CODE   LAN access code (Settings > WLAN on the printer)

Safety: starting a print and stopping a print need an explicit confirm=True, and
starting also needs bed_cleared=True. Temperatures are clamped to P1S limits.
"""
from __future__ import annotations

import base64
import ftplib
import json
import os
import socket
import ssl
import struct
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt
try:  # mcp >= 2
    from mcp.server.mcpserver import Image, MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP, Image

MAX_NOZZLE = 300  # P1S hotend limit
MAX_BED = 100  # P1S heatbed limit
SPEEDS = {"silent": 1, "standard": 2, "sport": 3, "ludicrous": 4}
FANS = {"part": 1, "aux": 2, "chamber": 3}
STAGES = {
    0: "printing", 1: "auto bed levelling", 2: "heatbed preheating", 3: "sweeping XY mech mode",
    4: "changing filament", 5: "paused (user)", 6: "filament runout", 7: "heating hotend",
    8: "calibrating extrusion", 9: "scanning bed surface", 10: "inspecting first layer",
    11: "identifying build plate type", 12: "calibrating micro lidar", 13: "homing",
    14: "cleaning nozzle tip", 15: "checking extruder temperature", 16: "paused (user)",
    17: "front cover falling", 18: "calibrating extrusion flow", 19: "paused (nozzle temp fault)",
    20: "paused (heatbed temp fault)", 255: "idle",
}


class P1S:
    """Thin client holding the merged MQTT report state."""

    def __init__(self, host: str, serial: str, access_code: str):
        self.host, self.serial, self.code = host, serial, access_code
        self.state: dict = {}
        self.last_report = 0.0
        self._seq = 0
        self._lock = threading.Lock()
        self._client: mqtt.Client | None = None
        self._connected = threading.Event()

    # ---- MQTT -----------------------------------------------------------
    def connect(self) -> None:
        if self._client and self._connected.is_set():
            return
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"claude-p1s-{os.getpid()}")
        c.username_pw_set("bblp", self.code)
        c.tls_set(cert_reqs=ssl.CERT_NONE)  # printer uses a self-signed cert
        c.tls_insecure_set(True)
        c.on_connect = self._on_connect
        c.on_disconnect = lambda *a, **k: self._connected.clear()
        c.on_message = self._on_message
        c.connect(self.host, 8883, keepalive=30)
        c.loop_start()
        self._client = c
        if not self._connected.wait(10):
            raise ConnectionError(f"MQTT connect to {self.host}:8883 timed out - check IP, LAN mode and access code")

    def _on_connect(self, client, _u, _f, rc, _p=None):
        if getattr(rc, "is_failure", rc != 0):
            return
        client.subscribe(f"device/{self.serial}/report")
        self._connected.set()

    def _on_message(self, _c, _u, msg):
        try:
            data = json.loads(msg.payload)
        except ValueError:
            return
        self.merge(data)

    def merge(self, data: dict) -> None:
        p = data.get("print")
        if isinstance(p, dict):
            with self._lock:
                self.state.update(p)  # P1 sends partial deltas; merge into full state
                self.last_report = time.time()

    def publish(self, payload: dict) -> None:
        self.connect()
        self._seq += 1
        for v in payload.values():
            v.setdefault("sequence_id", str(self._seq))
        info = self._client.publish(f"device/{self.serial}/request", json.dumps(payload), qos=1)
        info.wait_for_publish(5)

    def refresh(self, wait: float = 6.0) -> dict:
        """Ask for a full status dump and wait for it."""
        self.connect()
        before = self.last_report
        self.publish({"pushing": {"command": "pushall"}})
        end = time.time() + wait
        while time.time() < end and self.last_report == before:
            time.sleep(0.2)
        with self._lock:
            return dict(self.state)

    def gcode(self, *lines: str) -> None:
        self.publish({"print": {"command": "gcode_line", "param": "\n".join(lines) + "\n"}})

    # ---- FTPS -----------------------------------------------------------
    def _ftp(self) -> ftplib.FTP_TLS:
        class Implicit(ftplib.FTP_TLS):
            def connect(self, host="", port=0, timeout=-999, source_address=None):
                super().connect(host, port, timeout, source_address)
                self.sock = self.context.wrap_socket(self.sock, server_hostname=self.host)
                self.file = self.sock.makefile("r", encoding=self.encoding)
                return self.welcome

            def ntransfercmd(self, cmd, rest=None):
                conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
                if self._prot_p:
                    conn = self.context.wrap_socket(conn, server_hostname=self.host, session=self.sock.session)
                return conn, size

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        f = Implicit(context=ctx)
        f.connect(self.host, 990, timeout=30)
        f.login("bblp", self.code)
        f.prot_p()
        return f

    def upload(self, local: Path, remote_name: str) -> None:
        f = self._ftp()
        try:
            with local.open("rb") as fh:
                f.storbinary(f"STOR {remote_name}", fh)
        finally:
            try:
                f.quit()
            except Exception:
                f.close()

    def list_files(self) -> list[str]:
        f = self._ftp()
        try:
            out: list[str] = []
            for d in ("/", "/cache", "/model"):
                try:
                    out += [f"{d.rstrip('/')}/{n}" for n in f.nlst(d) if "." in n.rsplit("/", 1)[-1]]
                except ftplib.error_perm:
                    pass
            return out
        finally:
            f.close()

    # ---- Camera ---------------------------------------------------------
    def snapshot(self, timeout: float = 15.0) -> bytes:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        auth = struct.pack("<IIQ", 0x40, 0x3000, 0) + b"bblp".ljust(32, b"\0") + self.code.encode().ljust(32, b"\0")
        with socket.create_connection((self.host, 6000), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=self.host) as s:
                s.settimeout(timeout)
                s.sendall(auth)
                hdr = self._recv(s, 16)
                size = int.from_bytes(hdr[0:3], "little")
                jpg = self._recv(s, size)
        if not (jpg[:2] == b"\xff\xd8" and jpg[-2:] == b"\xff\xd9"):
            raise RuntimeError("camera returned a malformed JPEG (is LAN-mode liveview enabled?)")
        return jpg

    @staticmethod
    def _recv(s, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("camera stream closed")
            buf += chunk
        return buf


def summarize(st: dict) -> dict:
    """Condense the raw report into something readable."""
    ams_units = []
    for u in (st.get("ams") or {}).get("ams", []):
        ams_units.append({
            "unit": u.get("id"), "humidity_level": u.get("humidity"),
            "trays": [{"slot": t.get("id"), "type": t.get("tray_type"), "colour": t.get("tray_color"),
                       "remain_pct": t.get("remain"), "name": t.get("tray_sub_brands")} for t in u.get("tray", [])],
        })
    stage = st.get("stg_cur")
    return {
        "state": st.get("gcode_state"),
        "stage": STAGES.get(stage, stage),
        "file": st.get("subtask_name") or st.get("gcode_file"),
        "progress_pct": st.get("mc_percent"),
        "minutes_remaining": st.get("mc_remaining_time"),
        "layer": f'{st.get("layer_num")}/{st.get("total_layer_num")}',
        "nozzle_c": {"now": st.get("nozzle_temper"), "target": st.get("nozzle_target_temper")},
        "bed_c": {"now": st.get("bed_temper"), "target": st.get("bed_target_temper")},
        "chamber_c": st.get("chamber_temper"),
        "speed_level": st.get("spd_lvl"),
        "fans": {"part": st.get("cooling_fan_speed"), "aux": st.get("big_fan1_speed"), "chamber": st.get("big_fan2_speed")},
        "lights": {l.get("node"): l.get("mode") for l in st.get("lights_report", [])},
        "wifi_signal": st.get("wifi_signal"),
        "error_code": st.get("print_error"),
        "hms_alerts": st.get("hms"),
        "ams": ams_units,
        "tray_in_use": (st.get("ams") or {}).get("tray_now"),
    }


# ---------------------------------------------------------------------------
mcp = FastMCP("bambu-p1s")
_printer: P1S | None = None


def printer() -> P1S:
    global _printer
    if _printer is None:
        try:
            _printer = P1S(os.environ["P1S_HOST"], os.environ["P1S_SERIAL"], os.environ["P1S_ACCESS_CODE"])
        except KeyError as e:
            raise RuntimeError(f"Set {e.args[0]} (needs P1S_HOST, P1S_SERIAL, P1S_ACCESS_CODE)") from None
    return _printer


@mcp.tool()
def p1s_status() -> dict:
    """Live printer status: state, progress, ETA, temperatures, fans, lights, AMS slots, errors."""
    return summarize(printer().refresh())


@mcp.tool()
def p1s_raw_status() -> dict:
    """Full unprocessed status report from the printer (for debugging)."""
    return printer().refresh()


@mcp.tool()
def p1s_camera_snapshot() -> Image:
    """Take a JPEG snapshot from the chamber camera (use to inspect a print for spaghetti/warping)."""
    return Image(data=printer().snapshot(), format="jpeg")


@mcp.tool()
def p1s_pause() -> str:
    """Pause the current print."""
    printer().publish({"print": {"command": "pause"}})
    return "pause sent"


@mcp.tool()
def p1s_resume() -> str:
    """Resume a paused print."""
    printer().publish({"print": {"command": "resume"}})
    return "resume sent"


@mcp.tool()
def p1s_stop(confirm: bool = False) -> str:
    """Cancel the current print permanently. Requires confirm=True - ask the user first."""
    if not confirm:
        return "REFUSED: stopping discards the print. Ask the user, then call again with confirm=True."
    printer().publish({"print": {"command": "stop"}})
    return "stop sent"


@mcp.tool()
def p1s_set_light(on: bool, light: str = "chamber_light") -> str:
    """Turn the chamber light (or 'work_light') on/off."""
    if light not in ("chamber_light", "work_light"):
        raise ValueError("light must be chamber_light or work_light")
    printer().publish({"system": {"command": "ledctrl", "led_node": light, "led_mode": "on" if on else "off",
                                  "led_on_time": 500, "led_off_time": 500, "loop_times": 0, "interval_time": 0}})
    return f"{light} {'on' if on else 'off'}"


@mcp.tool()
def p1s_set_speed(profile: str) -> str:
    """Set print speed profile: silent, standard, sport or ludicrous."""
    lvl = SPEEDS.get(profile.lower())
    if not lvl:
        raise ValueError(f"profile must be one of {list(SPEEDS)}")
    printer().publish({"print": {"command": "print_speed", "param": str(lvl)}})
    return f"speed {profile}"


AUTO_SWITCH_BIT = 10  # home_flag bit reported for "AMS filament backup" (community-documented)


@mcp.tool()
def p1s_set_auto_refill(enabled: bool = True) -> dict:
    """Turn AMS filament backup (auto-refill) on/off so a print continues on a second spool when the first runs out.

    The backup spool only gets used if it matches the running one in material, brand AND colour (as
    entered in the AMS slot settings). Returns the printer's home_flag before/after so the change can be verified.
    """
    p = printer()
    before = p.refresh().get("home_flag")
    p.publish({"print": {"command": "print_option", "option": 0, "auto_switch_filament": bool(enabled)}})
    time.sleep(1.5)
    after = p.refresh().get("home_flag")
    bit = (after >> AUTO_SWITCH_BIT) & 1 if isinstance(after, int) else None
    return {"requested": enabled, "home_flag_before": before, "home_flag_after": after,
            "auto_switch_bit": bit,
            "verified": None if bit is None else bool(bit) == bool(enabled),
            "note": "If verified is false/None, set it on the printer: Settings > AMS > 'AMS filament backup'."}


@mcp.tool()
def p1s_check_refill_pairs() -> list[dict]:
    """List AMS slots that have a matching backup spool (same type, colour, brand) - i.e. which refills can happen."""
    ams = (printer().refresh().get("ams") or {}).get("ams", [])
    groups: dict[tuple, list[str]] = {}
    for u in ams:
        for t in u.get("tray", []):
            if t.get("tray_type"):
                key = (t.get("tray_type"), (t.get("tray_color") or "").upper(), t.get("tray_sub_brands") or "")
                groups.setdefault(key, []).append(f'unit{u.get("id")}/slot{int(t.get("id", 0)) + 1}')
    return [{"type": k[0], "colour": k[1], "brand": k[2], "slots": v, "refill_ready": len(v) > 1}
            for k, v in groups.items()]


@mcp.tool()
def p1s_set_temperature(nozzle_c: int | None = None, bed_c: int | None = None) -> str:
    """Set nozzle and/or bed target temperature (clamped to P1S limits: nozzle 300, bed 100). 0 = off."""
    lines, done = [], []
    if nozzle_c is not None:
        if not 0 <= nozzle_c <= MAX_NOZZLE:
            raise ValueError(f"nozzle must be 0-{MAX_NOZZLE}")
        lines.append(f"M104 S{nozzle_c}"); done.append(f"nozzle {nozzle_c}")
    if bed_c is not None:
        if not 0 <= bed_c <= MAX_BED:
            raise ValueError(f"bed must be 0-{MAX_BED}")
        lines.append(f"M140 S{bed_c}"); done.append(f"bed {bed_c}")
    if not lines:
        return "nothing to set"
    printer().gcode(*lines)
    return "set " + ", ".join(done) + " C"


@mcp.tool()
def p1s_set_fan(fan: str, percent: int) -> str:
    """Set a fan: part, aux or chamber, 0-100 %."""
    if fan not in FANS or not 0 <= percent <= 100:
        raise ValueError("fan in part/aux/chamber, percent 0-100")
    printer().gcode(f"M106 P{FANS[fan]} S{round(percent * 255 / 100)}")
    return f"{fan} fan {percent}%"


@mcp.tool()
def p1s_home() -> str:
    """Home all axes (G28). Make sure the bed is clear first."""
    printer().gcode("G28")
    return "homing"


@mcp.tool()
def p1s_send_gcode(gcode: str, confirm: bool = False) -> str:
    """Send raw G-code lines. Requires confirm=True. Refused while a print is running."""
    p = printer()
    if not confirm:
        return "REFUSED: raw G-code can crash the toolhead. Show the user the code, then call with confirm=True."
    if p.refresh().get("gcode_state") in ("RUNNING", "PAUSE"):
        return "REFUSED: a print is active."
    p.gcode(*[l for l in gcode.splitlines() if l.strip()])
    return "sent"


@mcp.tool()
def p1s_list_files() -> list[str]:
    """List .3mf/.gcode files stored on the printer (SD card / cache)."""
    return printer().list_files()


@mcp.tool()
def p1s_upload(local_path: str) -> str:
    """Upload a sliced .gcode.3mf (exported from Bambu Studio via 'Export plate sliced file') to the printer."""
    p = Path(local_path).expanduser()
    if not p.is_file() or not p.name.endswith(".3mf"):
        raise ValueError("local_path must be an existing sliced .3mf file")
    printer().upload(p, p.name)
    return f"uploaded {p.name}"


@mcp.tool()
def p1s_start_print(
    filename: str,
    bed_cleared: bool = False,
    confirm: bool = False,
    plate: int = 1,
    use_ams: bool = True,
    ams_slots: list[int] | None = None,
    bed_leveling: bool = True,
    flow_cali: bool = True,
    timelapse: bool = False,
) -> str:
    """Start printing a sliced .gcode.3mf already on the printer (see p1s_upload / p1s_list_files).

    Before calling: the user must confirm the build plate is clear, the right plate type is fitted,
    and the AMS slot mapping is correct. Requires bed_cleared=True AND confirm=True.
    ams_slots maps filament 1..n in the file to AMS slot numbers 0-3 (e.g. [0, 2]).
    """
    if not (bed_cleared and confirm):
        return ("REFUSED: need the user's explicit go-ahead. Confirm (1) bed is clear, (2) correct plate fitted, "
                "(3) AMS slot mapping, then call with bed_cleared=True and confirm=True.")
    p = printer()
    state = p.refresh().get("gcode_state")
    if state in ("RUNNING", "PAUSE", "PREPARE"):
        return f"REFUSED: printer is busy ({state})."
    payload = {"print": {
        "command": "project_file", "param": f"Metadata/plate_{plate}.gcode",
        "project_id": "0", "profile_id": "0", "task_id": "0", "subtask_id": "0",
        "subtask_name": filename, "url": f"file:///sdcard/{filename}",
        "timelapse": timelapse, "bed_type": "auto", "bed_leveling": bed_leveling,
        "flow_cali": flow_cali, "vibration_cali": True, "layer_inspect": False,
        "use_ams": use_ams, "ams_mapping": ams_slots or [0],
    }}
    p.publish(payload)
    return f"print of {filename} requested - poll p1s_status to confirm it started"


if __name__ == "__main__":
    mcp.run()
