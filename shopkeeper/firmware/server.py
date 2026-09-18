"""
HTTP server and JSON API.

Hand-rolled rather than a framework: MicroPython's asyncio gives a stream
server for free, and the whole surface is nine routes. The one non-obvious
piece is that index.html is STREAMED off flash in chunks instead of being read
into a string - the page is ~30 KB and the S3 has plenty of heap, but reading a
whole file to serve it is the habit that falls over the moment somebody adds a
photo to the UI.
"""
try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

import json
import time
import gc

import config
import store

_MIME = {"html": "text/html; charset=utf-8", "json": "application/json",
         "ico": "image/x-icon", "svg": "image/svg+xml"}


class App:
    def __init__(self, drawers, log):
        self.drawers = drawers
        self.by_id = {d.id: d for d in drawers}
        self.log = log
        self.unlocked_at = 0
        self.boot_at = time.time()
        self.net = "-"
        self.cmd = None
        self.limits = {}      # {drawer_id: {"low": us, "high": us}}
        self.cal_dir = {}     # which end each drawer is currently searching

    # ── access ────────────────────────────────────────────────────────────
    @property
    def locked(self):
        if not getattr(config, "REQUIRE_PIN", True):
            return False                      # bench mode
        if self.unlocked_at == 0:
            return True
        return time.time() - self.unlocked_at > config.PIN_TIMEOUT_S

    def touch(self):
        if self.unlocked_at:
            self.unlocked_at = time.time()

    def unlock(self, pin):
        if str(pin) != str(config.PIN):
            self.log.add("PIN REJECTED")
            return False
        self.unlocked_at = time.time()
        self.log.add("UNLOCKED")
        return True

    def lock(self):
        self.unlocked_at = 0
        self.log.add("LOCKED")

    # ── state ─────────────────────────────────────────────────────────────
    def state(self):
        return {
            "unit": config.UNIT, "fw": config.FW, "site": config.SITE,
            "bypass": not getattr(config, "REQUIRE_PIN", True),
            "net": self.net,
            "locked": self.locked,
            "timeout": config.PIN_TIMEOUT_S,
            "left": 0 if self.locked else
                    max(0, config.PIN_TIMEOUT_S - int(time.time() - self.unlocked_at)),
            "uptime": time.time() - self.boot_at,
            "mem": gc.mem_free(),
            "drawers": [dict(d.state(), tools=store.tools_for(d.id))
                        for d in self.drawers],
            "log": self.log.entries[:24],
            "limits": {str(k): v for k, v in self.limits.items()},
        }


# ── tiny HTTP plumbing ─────────────────────────────────────────────────────
async def _send(w, code, body=b"", ctype="application/json", extra=""):
    if isinstance(body, str):
        body = body.encode()
    w.write("HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
            "Cache-Control: no-store\r\nConnection: close\r\n{}\r\n"
            .format(code, ctype, len(body), extra))
    if body:
        w.write(body)
    await w.drain()


async def _send_file(w, path, ctype):
    try:
        size = 0
        with open(path, "rb") as fh:
            while True:
                b = fh.read(512)
                if not b:
                    break
                size += len(b)
        w.write("HTTP/1.1 200 OK\r\nContent-Type: {}\r\nContent-Length: {}\r\n"
                "Cache-Control: no-store\r\nConnection: close\r\n\r\n"
                .format(ctype, size))
        with open(path, "rb") as fh:
            while True:
                b = fh.read(512)
                if not b:
                    break
                w.write(b)
                await w.drain()
    except OSError:
        await _send(w, "404 Not Found", b'{"error":"missing"}')


def _json(app, obj):
    return json.dumps(obj)


async def handle(app, r, w):
    try:
        line = await asyncio.wait_for(r.readline(), 5)
        if not line:
            return
        parts = line.decode().split()
        if len(parts) < 2:
            return
        method, target = parts[0], parts[1]
        path, _, qs = target.partition("?")

        clen = 0
        while True:
            h = await r.readline()
            if not h or h == b"\r\n":
                break
            hl = h.decode().lower()
            if hl.startswith("content-length:"):
                try:
                    clen = int(hl.split(":", 1)[1].strip())
                except ValueError:
                    clen = 0
        body = {}
        if clen:
            raw = await r.readexactly(min(clen, 1024))
            try:
                body = json.loads(raw)
            except ValueError:
                body = {}

        # ── routes ────────────────────────────────────────────────────────
        if path == "/" or path == "/index.html":
            return await _send_file(w, "/www/index.html", _MIME["html"])

        if path == "/api/state":
            return await _send(w, "200 OK", _json(app, app.state()))

        if path == "/api/unlock" and method == "POST":
            ok = app.unlock(body.get("pin", ""))
            return await _send(w, "200 OK" if ok else "403 Forbidden",
                               _json(app, {"ok": ok, "locked": app.locked}))

        if path == "/api/lock" and method == "POST":
            app.lock()
            return await _send(w, "200 OK", _json(app, {"ok": True}))

        # everything past here needs an unlocked cabinet
        if path.startswith("/api/"):
            if app.locked:
                return await _send(w, "403 Forbidden",
                                   _json(app, {"ok": False, "error": "locked"}))
            app.touch()

        if path == "/api/drawer" and method == "POST":
            d = app.by_id.get(int(body.get("id", -1)))
            if d is None:
                return await _send(w, "404 Not Found", _json(app, {"ok": False}))
            if d.busy:
                return await _send(w, "409 Conflict",
                                   _json(app, {"ok": False, "error": "moving"}))
            want = bool(body.get("open"))
            asyncio.create_task(_run_move(app, d, want, body.get("tool", "")))
            return await _send(w, "202 Accepted", _json(app, {"ok": True}))

        if path == "/api/cal" and method == "POST":
            d = app.by_id.get(int(body.get("id", -1)))
            if d is None:
                return await _send(w, "404 Not Found", _json(app, {"ok": False}))
            if "jog_us" in body:
                asyncio.create_task(d.jog(int(body["jog_us"])))
            else:
                d.calibrate(body.get("closed_us"), body.get("open_us"))
                store.save_cal(app.drawers)
                app.log.add("CALIBRATED", d.id,
                            "{}..{} us".format(d.closed_us, d.open_us))
            # no {**a, "b": 1} here: MicroPython's parser rejects dict unpacking
            # inside a display, and it fails at IMPORT time, not on this line
            st = d.state()
            st["ok"] = True
            return await _send(w, "200 OK", _json(app, st))

        # ── guided limit search ───────────────────────────────────────────
        if path == "/api/autocal" and method == "POST":
            d = app.by_id.get(int(body.get("id", -1)))
            if d is None:
                return await _send(w, "404 Not Found", _json(app, {"ok": False}))
            up = bool(body.get("up"))
            asyncio.create_task(d.walk(up))
            app.cal_dir[d.id] = "high" if up else "low"
            return await _send(w, "202 Accepted", _json(app, {"ok": True}))

        if path == "/api/autocal/mark" and method == "POST":
            d = app.by_id.get(int(body.get("id", -1)))
            if d is None or not d.walking:
                return await _send(w, "409 Conflict",
                                   _json(app, {"ok": False, "error": "not searching"}))
            limit = d.mark()
            side = app.cal_dir.get(d.id)
            app.limits.setdefault(d.id, {})[side] = limit
            got = app.limits[d.id]
            # once both ends are known the machine sets itself up: the endpoint
            # nearer the mechanism's closed position is whichever the operator
            # found first is NOT assumed - both are stored and the wider span
            # is applied, direction left to the drawer's own config
            if "low" in got and "high" in got:
                d.calibrate(got["low"], got["high"])
                store.save_cal(app.drawers)
                app.log.add("CALIBRATED", d.id,
                            "{}..{} us".format(d.closed_us, d.open_us))
            st = d.state()
            st["ok"] = True
            st["limits"] = got
            return await _send(w, "200 OK", _json(app, st))

        if path == "/api/log" and method == "DELETE":
            app.log.clear()
            return await _send(w, "200 OK", _json(app, {"ok": True}))

        return await _send(w, "404 Not Found", _json(app, {"error": "no route"}))

    except Exception as e:            # never let one bad request kill the server
        try:
            await _send(w, "500 Internal Server Error",
                        json.dumps({"error": str(e)}))
        except Exception:
            pass
    finally:
        try:
            await w.wait_closed()
        except Exception:
            pass


async def _run_move(app, d, want, tool):
    # Tell the panel a command arrived from the network BEFORE moving, so the
    # screen leads the drawer. The scripted demo drives Servo.move() directly
    # and never lands here, which is what keeps "somebody pressed a button"
    # distinguishable from "the cabinet is performing".
    app.cmd = {"id": d.id, "label": "BAY " + str(d.id + 1),
               "verb": "OPENING" if want else "SECURING",
               "pos": d.pos, "done": False, "at": time.time()}
    await d.move(want)
    app.log.add("OPENED" if want else "CLOSED", d.id, tool or "")
    app.log.maybe_flush()
    app.cmd = {"id": d.id, "label": "BAY " + str(d.id + 1),
               "verb": "OPEN" if want else "SECURED",
               "pos": 1.0 if want else 0.0, "done": True, "at": time.time()}


async def serve(app, port=80):
    await asyncio.start_server(lambda r, w: handle(app, r, w), "0.0.0.0", port)
