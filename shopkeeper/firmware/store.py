"""
Persistence: calibration, tool register, and the access log.

The log is the product. The ~20 lakh cabinets do not sense anything either - no
load cells, no cameras, no RFID - so what a shop is actually buying is a locked
drawer plus an answer to "who had it last". That answer has to survive a power
cut, which is the only reason any of this touches flash.

Writes are batched and rate-limited: the ESP32's flash wears out, and a demo
that gets opened two hundred times in an afternoon should not spend that
budget.
"""
import json
import os
import time

import config

_CAL = config.DATA_DIR + "/cal.json"
_LOG = config.DATA_DIR + "/log.json"


def _ensure_dir():
    try:
        os.mkdir(config.DATA_DIR)
    except OSError:
        pass                      # already there


def _read(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write(path, obj):
    _ensure_dir()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as fh:
            json.dump(obj, fh)
        # rename is atomic on littlefs, so a power cut mid-write leaves the old
        # file intact rather than a half-written one
        try:
            os.remove(path)
        except OSError:
            pass
        os.rename(tmp, path)
        return True
    except OSError:
        return False


# ── calibration ────────────────────────────────────────────────────────────
def load_cal():
    return _read(_CAL, {})


def save_cal(drawers):
    return _write(_CAL, {str(d.id): [d.closed_us, d.open_us] for d in drawers})


# ── log ────────────────────────────────────────────────────────────────────
class Log:
    def __init__(self):
        self.entries = _read(_LOG, [])
        if not isinstance(self.entries, list):
            self.entries = []
        self._dirty = False
        self._last_flush = time.ticks_ms()

    def add(self, what, drawer=None, detail=""):
        self.entries.insert(0, {
            "t": time.time(),
            "up": time.ticks_ms() // 1000,
            "what": what,
            "drawer": drawer,
            "detail": detail,
        })
        del self.entries[config.LOG_MAX:]
        self._dirty = True

    def maybe_flush(self, force=False):
        """Flash has a finite number of erase cycles; a demo can easily rack up
        hundreds of events an hour. Coalesce to at most one write every 20 s."""
        if not self._dirty:
            return False
        if not force and time.ticks_diff(time.ticks_ms(), self._last_flush) < 20_000:
            return False
        ok = _write(_LOG, self.entries)
        if ok:
            self._dirty = False
            self._last_flush = time.ticks_ms()
        return ok

    def clear(self):
        self.entries = []
        self._dirty = True
        self.maybe_flush(force=True)


# ── tools ──────────────────────────────────────────────────────────────────
def tools_for(drawer_id):
    return config.TOOLS.get(drawer_id, [])
