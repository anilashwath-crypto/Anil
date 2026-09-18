#!/usr/bin/env python3
"""
Desktop mock of the shopkeeper NANO firmware.

Serves the REAL www/index.html against a simulated cabinet, so the kiosk UI can
be demoed and worked on without joining the cabinet's access point — which on a
laptop means giving up your internet connection.

It imports the real config.py, so tool lists, PIN, timeouts and servo endpoints
are the ones the hardware actually runs. The only thing faked is the servo: a
move takes TRAVEL_MS of wall clock and then the drawer is somewhere else, which
is all the UI can observe anyway.

    python3 firmware/mock_server.py [--port 8732]
"""
import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config                                            # noqa: E402

WWW = os.path.join(HERE, "www")
BOOT = time.time()


class Drawer:
    def __init__(self, spec):
        self.id = spec["id"]
        self.name = spec["name"]
        self.pin = spec["pin"]
        self.closed_us = spec["closed_us"]
        self.open_us = spec["open_us"]
        self.is_open = False
        self.busy = False
        self.powered = False
        self.cycles = 0
        self.pos = 0.0

    @property
    def travel_mm(self):
        return round(config.TRAVEL_MM * abs(self.open_us - self.closed_us)
                     / 2000.0, 1)

    def state(self):
        return {"id": self.id, "name": self.name, "pin": self.pin,
                "open": self.is_open, "busy": self.busy,
                "closed_us": self.closed_us, "open_us": self.open_us,
                "travel_mm": self.travel_mm, "powered": self.powered,
                "cycles": self.cycles, "pos": round(self.pos, 3),
                "us": int(self.closed_us + self.pos *
                          (self.open_us - self.closed_us)),
                "deg": round(abs(self.open_us - self.closed_us) / 2000.0 * 180, 1),
                # servo.py reports this and the limit finder reads it; without
                # it the mock's drawer dict was one key short of the hardware's
                "walking": False}

    def move(self, opened, log):
        """Same shape as the firmware: returns immediately, finishes later."""
        if self.busy:
            return False
        self.busy = True
        self.powered = True

        def run():
            # step the position so the elevation animates exactly as it does
            # on the hardware, where pos comes off the servo glide
            n, t0 = 26, self.pos
            for i in range(n + 1):
                f = i / n
                f = 4*f*f*f if f < .5 else 1 - ((-2*f+2)**3)/2
                self.pos = t0 + ((1.0 if opened else 0.0) - t0) * f
                time.sleep(config.TRAVEL_MS / 1000.0 / n)
            self.pos = 1.0 if opened else 0.0
            if opened:
                self.cycles += 1
            self.is_open = opened
            self.busy = False
            log.add("OPENED" if opened else "CLOSED", self.id)
            time.sleep(config.DETACH_AFTER_MS / 1000.0)
            self.powered = False        # the real one cuts the signal here too

        threading.Thread(target=run, daemon=True).start()
        return True


class Log:
    def __init__(self):
        self.entries = []
        self.lock = threading.Lock()

    def add(self, what, drawer=None, detail=""):
        with self.lock:
            self.entries.insert(0, {
                "t": time.time(), "up": int(time.time() - BOOT),
                "what": what, "drawer": drawer, "detail": detail})
            del self.entries[config.LOG_MAX:]


class Cabinet:
    def __init__(self):
        self.drawers = [Drawer(s) for s in config.DRAWERS]
        self.by_id = {d.id: d for d in self.drawers}
        self.log = Log()
        self.unlocked_at = 0
        self.log.add("BOOT", None, "MOCK:" + os.uname().nodename)

    @property
    def locked(self):
        # Same rule as server.py, including REQUIRE_PIN. Without this the mock
        # could never reproduce bench mode, so the loud BYPASSED chip - the one
        # piece of UI that exists to stop this cabinet being demonstrated with
        # its lock off - was untestable anywhere except on the hardware.
        if not getattr(config, "REQUIRE_PIN", True):
            return False
        if not self.unlocked_at:
            return True
        return time.time() - self.unlocked_at > config.PIN_TIMEOUT_S

    def state(self):
        # Key set must match server.py's state() exactly. It did not: "bypass"
        # and "limits" were missing here, so the UI's bench-mode chip and the
        # limit finder both read undefined against the mock and only came right
        # on the board - which is precisely backwards for a development target.
        return {"unit": config.UNIT, "fw": config.FW, "site": config.SITE,
                "bypass": not getattr(config, "REQUIRE_PIN", True),
                "net": "AP:" + config.AP_SSID,
                "locked": self.locked, "timeout": config.PIN_TIMEOUT_S,
                "left": 0 if self.locked else max(0, config.PIN_TIMEOUT_S -
                        int(time.time() - self.unlocked_at)),
                "uptime": int(time.time() - BOOT), "mem": 2029856,
                "drawers": [dict(d.state(), tools=config.TOOLS.get(d.id, []))
                            for d in self.drawers],
                "log": self.log.entries[:24],
                "limits": {}}


CAB = Cabinet()


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass                                   # quiet; the UI polls constantly

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except ValueError:
            return {}

    # ── routes, mirroring server.py exactly ──────────────────────────────
    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            try:
                with open(os.path.join(WWW, "index.html"), "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            except OSError:
                return self._send(404, {"error": "no index.html"})
        if p == "/api/state":
            return self._send(200, CAB.state())
        return self._send(404, {"error": "no route"})

    def do_DELETE(self):
        if self.path == "/api/log":
            if CAB.locked:
                return self._send(403, {"ok": False, "error": "locked"})
            CAB.log.entries = []
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "no route"})

    def do_POST(self):
        p = self.path.split("?")[0]
        b = self._body()

        if p == "/api/unlock":
            ok = str(b.get("pin", "")) == str(config.PIN)
            CAB.log.add("UNLOCKED" if ok else "PIN REJECTED")
            if ok:
                CAB.unlocked_at = time.time()
            return self._send(200 if ok else 403,
                              {"ok": ok, "locked": CAB.locked})

        if p == "/api/lock":
            CAB.unlocked_at = 0
            CAB.log.add("LOCKED")
            return self._send(200, {"ok": True})

        if CAB.locked:
            return self._send(403, {"ok": False, "error": "locked"})
        CAB.unlocked_at = time.time()

        if p == "/api/drawer":
            d = CAB.by_id.get(int(b.get("id", -1)))
            if d is None:
                return self._send(404, {"ok": False})
            if d.busy:
                return self._send(409, {"ok": False, "error": "moving"})
            d.move(bool(b.get("open")), CAB.log)
            return self._send(202, {"ok": True})

        if p == "/api/cal":
            d = CAB.by_id.get(int(b.get("id", -1)))
            if d is None:
                return self._send(404, {"ok": False})
            if "jog_us" in b:
                d.powered = True
                return self._send(200, dict(d.state(), ok=True))
            if b.get("closed_us") is not None:
                d.closed_us = int(b["closed_us"])
            if b.get("open_us") is not None:
                d.open_us = int(b["open_us"])
            CAB.log.add("CALIBRATED", d.id,
                        "%d..%d us" % (d.closed_us, d.open_us))
            return self._send(200, dict(d.state(), ok=True))

        return self._send(404, {"error": "no route"})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8732)
    a = ap.parse_args()
    print("shopkeeper NANO — MOCK cabinet")
    print("  serving the real www/index.html")
    print("  PIN %s   drawers %d   travel %s mm"
          % (config.PIN, len(CAB.drawers), CAB.drawers[0].travel_mm))
    print("  http://127.0.0.1:%d/" % a.port)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
