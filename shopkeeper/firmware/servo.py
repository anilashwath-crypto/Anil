"""
SG90 driver.

Two things here are not obvious and both were learned the hard way on hobby
servos:

1. A hobby servo holds position by hunting - it never stops correcting, so it
   buzzes and draws current forever. Cutting the signal after the move lets it
   go quiet. The rack and pinion is not backdriveable enough for a drawer to
   creep open on its own, so nothing is lost by doing it.

2. Commanding the full 500..2500 us span asks for 180 deg, and most SG90 clones
   physically reach 160-175 before the output arm hits its own end stop. Past
   that the pot is out of range, the loop never reaches its target, and the
   motor stalls at full current until something gives. So the endpoints are
   configuration, not constants, and the defaults are deliberately short.
"""
try:
    import asyncio
except ImportError:                      # MicroPython < 1.21
    import uasyncio as asyncio

from machine import Pin, PWM
import config


def _ease(t):
    """Cubic in-out. A drawer that glides reads as a product."""
    if t < 0.5:
        return 4 * t * t * t
    p = -2 * t + 2
    return 1 - (p * p * p) / 2


class Servo:
    def __init__(self, spec):
        self.id = spec["id"]
        self.name = spec["name"]
        self.pin = spec["pin"]
        self.closed_us = spec["closed_us"]
        self.open_us = spec["open_us"]
        self._pwm = None
        self._us = self.closed_us
        self.is_open = False
        self.busy = False
        self.cycles = 0            # completed opens, for the maintenance readout
        Pin(self.pin, Pin.OUT).value(0)   # defined from the very first moment
        self.pos = 0.0             # 0..1 through the stroke, live during a move
        self.walking = False       # a limit search is in progress
        self.walk_stop = False
        self.walk_hit = None
        self._detach_task = None

    # ── low level ─────────────────────────────────────────────────────────
    def _attach(self):
        if self._pwm is None:
            self._pwm = PWM(Pin(self.pin), freq=config.SERVO_FREQ_HZ)

    def detach(self):
        """Stop driving, but HOLD THE LINE LOW - never leave it floating.

        deinit() alone returns the pin to high-impedance. A servo whose signal
        wire is floating picks up noise off the neighbouring wire and twitches,
        which looks exactly like "the other drawer moved too" - and that is a
        far more convincing bug than it deserves to be, because the servo that
        was actually commanded really did move at the same moment.

        A steady low is not a valid servo frame, so the servo simply holds
        station and stays quiet."""
        if self._pwm is not None:
            try:
                self._pwm.deinit()
            except Exception:
                pass
            self._pwm = None
        try:
            Pin(self.pin, Pin.OUT).value(0)
        except Exception:
            pass

    def _write_us(self, us):
        lo = min(self.closed_us, self.open_us) - 1
        hi = max(self.closed_us, self.open_us) + 1
        if us < lo:
            us = lo
        elif us > hi:
            us = hi
        self._attach()
        # duty_ns is exact; duty_u16 quantises the pulse badly at 50 Hz
        try:
            self._pwm.duty_ns(int(us * 1000))
        except AttributeError:
            self._pwm.duty_u16(int(us * 65535 * config.SERVO_FREQ_HZ / 1_000_000))
        self._us = us

    # ── moves ─────────────────────────────────────────────────────────────
    async def _glide(self, to_us, ms):
        frm = self._us
        if frm == to_us:
            self._write_us(to_us)
            return
        steps = max(8, int(ms / 20))
        span = self.open_us - self.closed_us
        for i in range(steps + 1):
            us = frm + (to_us - frm) * _ease(i / steps)
            self._write_us(us)
            # live stroke fraction, so the UI can draw the drawer where it
            # actually is rather than only where it will end up
            self.pos = 0.0 if span == 0 else (us - self.closed_us) / span
            await asyncio.sleep_ms(int(ms / steps))

    async def _settle_then_detach(self):
        await asyncio.sleep_ms(config.DETACH_AFTER_MS)
        self.detach()

    async def move(self, opened, ms=None):
        """Drive to the open or closed endpoint. Returns when the move is done;
        the detach happens on its own afterwards."""
        if self.busy:
            return False
        self.busy = True
        try:
            await self._glide(self.open_us if opened else self.closed_us,
                              config.TRAVEL_MS if ms is None else ms)
            self.is_open = opened
            self.pos = 1.0 if opened else 0.0
            if opened:
                self.cycles += 1
        finally:
            self.busy = False
        asyncio.create_task(self._settle_then_detach())
        return True

    async def walk(self, up, step=25, dwell_ms=240, lo=500, hi=2500):
        """Creep outward from centre until told to stop.

        This is how the limits get found. The ESP32 cannot sense a stall - an
        SG90 is open loop, there is no encoder and no shunt - so the machine
        drives the search and a human supplies the one bit of information the
        hardware physically cannot: "that is as far as it goes". Everything
        after that (backoff, travel, sweep angle, persistence) is automatic.

        Deliberately slow: 25 us a step with a 240 ms dwell is about 2 deg per
        third of a second, which is slow enough to hear the motor change note
        before any damage is done."""
        if self.busy or self.walking:
            return False
        self.busy = True
        self.walking = True
        self.walk_stop = False
        self.walk_hit = None
        try:
            us = 1500
            self._write_us(us)
            await asyncio.sleep_ms(500)
            while not self.walk_stop:
                us = us + step if up else us - step
                if us > hi or us < lo:
                    self.walk_hit = hi if up else lo      # hit the electrical end
                    break
                self._write_us(us)
                await asyncio.sleep_ms(dwell_ms)
            if self.walk_hit is None:
                self.walk_hit = int(self._us)
        finally:
            self.walking = False
            self.busy = False
        asyncio.create_task(self._settle_then_detach())
        return True

    def mark(self, backoff=60):
        """Stop the walk and take the current position as the limit, minus a
        safety backoff so the servo never sits on its own end stop."""
        if not self.walking:
            return None
        self.walk_stop = True
        raw = int(self._us)
        return raw - backoff if raw > 1500 else raw + backoff

    async def jog(self, us):
        """Hold one raw pulse width. Calibration only - this is the mode that
        can drive the mechanism into its own end stop, so the UI keeps it
        behind the calibration panel."""
        if self.busy:
            return False
        self.busy = True
        try:
            self._write_us(us)
            await asyncio.sleep_ms(260)
        finally:
            self.busy = False
        asyncio.create_task(self._settle_then_detach())
        return True

    def calibrate(self, closed_us=None, open_us=None):
        if closed_us is not None:
            self.closed_us = int(closed_us)
        if open_us is not None:
            self.open_us = int(open_us)
        self._us = self.closed_us if not self.is_open else self.open_us

    # ── reporting ─────────────────────────────────────────────────────────
    @property
    def travel_mm(self):
        """Millimetres the drawer actually moves for the commanded span.

        180 deg of the pinion is pi * config.PITCH_R. The default
        endpoints are 650..2350, a span of 1700 us out of the 2000 us that maps
        to 180 deg - so 153 deg, so 26.7 mm. The remaining 4.7 mm is why the
        drawer does not come all the way out, and that is deliberate."""
        span = abs(self.open_us - self.closed_us)
        return config.TRAVEL_MM * (span / 2000.0)

    def state(self):
        return {
            "id": self.id, "name": self.name, "pin": self.pin,
            "open": self.is_open, "busy": self.busy,
            "closed_us": self.closed_us, "open_us": self.open_us,
            "travel_mm": round(self.travel_mm, 1),
            "powered": self._pwm is not None,
            "cycles": self.cycles,
            "pos": round(self.pos, 3),
            "us": int(self._us),
            "deg": round(abs(self.open_us - self.closed_us) / 2000.0 * 180, 1),
            "walking": self.walking,
        }
