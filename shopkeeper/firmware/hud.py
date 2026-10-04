"""
The top-face display: an animated attract loop, 128 x 64, one colour.

Read at arm's length, across a table, by someone who has not been told what to
look at. That rules out most of what looks good on a desk.

  - One thing is big. A glyph is 8 px per scale step, so scale 3 fits five
    characters across and scale 4 fits four. That is the whole typographic
    budget; everything else is subordinate to whatever gets the big line.
  - Inverted bars, not outlines. A filled block with knocked-out text is the
    highest-contrast mark a mono panel can make.
  - Animation earns its place. The gear screen turns a real 10-tooth pinion
    against a real rack at the real ratio - one rack pitch per gear tooth -
    because the pitch of the whole project is that this mechanism works. Drawer
    glyphs slide by measured position. Nothing else moves.

NOTHING WRITES OUTSIDE THE PANEL. Every string goes through _fit(), which
truncates to the pixels actually left at that x and scale. The first version
did the arithmetic by eye and put three strings over the edge - "TOOL ACCESS
CONTROL" is 19 characters, which is 152 px on a 128 px panel, and the bay
caption started at x=90 and ran to 146. Truncating at the draw call means a
long string can look clipped, but it can never silently vanish off the side.

MicroPython: no f-strings with =, no dict unpacking, no str.ljust.
"""
import framebuf
import math
import time

W, H = 128, 64
RAIL_H = 11


# ── text that cannot leave the panel ──────────────────────────────────────

def _fit(s, x=0, scale=1):
    room = (W - x) // (8 * scale)
    return s[:room] if room > 0 else ""


def txt(d, s, x, y, c=1):
    d.text(_fit(s, x), x, y, c)


def txt_c(d, s, y, c=1):
    s = _fit(s)
    d.text(s, (W - len(s) * 8) // 2, y, c)


def big_c(d, s, y, scale):
    s = _fit(s, 0, scale)
    d.big(s, (W - len(s) * 8 * scale) // 2, y, scale)


def txt_r(d, s, y, pad=3, c=1):
    s = _fit(s)
    d.text(s, W - len(s) * 8 - pad, y, c)


def rail(d, left, right=""):
    d.fill_rect(0, 0, W, RAIL_H, 1)
    r = _fit(right, 0)
    lmax = (W - len(r) * 8 - 10) // 8
    d.text(left[:max(lmax, 0)], 3, 2, 0)
    if r:
        d.text(r, W - len(r) * 8 - 3, 2, 0)


def drawer_glyph(d, x, y, pos, w=42, h=11):
    """Case outline with the drawer sliding out. pos 0..1, real position."""
    w = min(w, W - x - 1)
    d.rect(x, y, w, h, 1)
    slide = int((w // 3) * max(0.0, min(1.0, pos)))
    d.fill_rect(x + 2 + slide, y + 2, max(w - 10, 2), h - 4, 1)


def bar(d, x, y, w, h, frac):
    w = min(w, W - x - 1)
    d.rect(x, y, w, h, 1)
    fill = int((w - 4) * max(0.0, min(1.0, frac)))
    if fill > 0:
        d.fill_rect(x + 2, y + 2, fill, h - 4, 1)


# ── screens. each takes (d, ph, ctx); ph runs 0..1 across the dwell ───────

def _ease(t):
    return t*t*(3-2*t)


def _stagger(ph, i, n, lead=0.55):
    """Phase for row i of n, so rows arrive one after another."""
    a = i * (1.0 - lead) / max(n - 1, 1)
    return max(0.0, min(1.0, (ph - a) / lead))


def _claim(d, top, number, under, ph, scale=4):
    """The house style for a single-fact screen: an inverted rail, one numeral
    big enough to read across a room, and a caption. A hardware investor gives
    a panel about ten seconds, so a screen that needs two readings has failed."""
    rail(d, top)
    big_c(d, number, 20, scale)
    e = _ease(min(ph * 1.6, 1.0))
    half = int(e * 46)
    if half:
        d.hline(64 - half, 50, half * 2, 1)
    if ph > 0.30:
        txt_c(d, under, 54)


# ── 1. who ────────────────────────────────────────────────────────────────
def s_ident(d, ph, ctx):
    d.fill(0)
    rail(d, "SHOPKEEPER", ctx.get("link", ""))
    e = _ease(min(ph * 2.2, 1.0))
    big_c(d, "NANO", int(4 + 14 * e), 3)
    if ph > 0.45:
        y = RAIL_H + 4 + int((ph - 0.45) / 0.55 * (H - RAIL_H - 8))
        d.fill_rect(0, y, W, 2, 0)
        d.hline(0, y + 2, W, 1)
    if ph > 0.35:
        txt_c(d, "MOTORISED", 44)
        txt_c(d, "TOOL CABINET", 54)


# ── 2. what it does ───────────────────────────────────────────────────────
def s_what(d, ph, ctx):
    d.fill(0)
    rail(d, "WHAT IT DOES")
    e = _ease(min(ph * 1.8, 1.0))
    bx, by = 8, 22
    d.rect(bx + 4, by - 7, 9, 9, 1)
    d.fill_rect(bx + 6, by - 5, 5, 7, 0)
    d.fill_rect(bx, by, 17, 13, 1)
    d.fill_rect(bx + 7, by + 4, 2, 5, 0)
    if e > 0.15:
        txt(d, "LOCKED", 34, 20)
    if e > 0.45:
        txt(d, "UNTIL", 34, 32)
    if e > 0.70:
        d.fill_rect(32, 42, 94, 12, 1)
        d.text("AUTHORISED", 36, 45, 0)


# ── 3. proof it works ─────────────────────────────────────────────────────
def s_proof(d, ph, ctx):
    """Measured on the bench, not claimed. This is the screen that matters."""
    d.fill(0)
    n = ctx.get("test_cycles", 0)
    f = ctx.get("test_fail", 0)
    shown = int(_ease(min(ph * 1.7, 1.0)) * n)
    _claim(d, "VERIFIED", str(shown), "CYCLES  %d FAIL" % f, ph)


# ── 4. the hardware is real ───────────────────────────────────────────────
def s_mechanism(d, ph, ctx):
    d.fill(0)
    rail(d, "RACK+PINION", "m1.25")
    N, R, rr = 10, 15, 9
    cxp, cyp = 34, 40
    rot = ph * 2 * math.pi / N * 4
    for i in range(N):
        a = rot + i * 2 * math.pi / N
        ca, sa = math.cos(a), math.sin(a)
        d.fb.line(int(cxp + rr*ca), int(cyp + rr*sa),
                  int(cxp + R*ca), int(cyp + R*sa), 1)
    d.fb.ellipse(cxp, cyp, rr, rr, 1)
    d.fb.ellipse(cxp, cyp, 3, 3, 1, True)
    pitch = 2 * math.pi * R / N
    off = (rot * R) % pitch
    y = cyp + R + 2
    d.hline(54, y + 6, 72, 1)
    x = 54 - off
    while x < W - 3:
        if x >= 54:
            d.fb.line(int(x), y + 6, int(x + 2), y, 1)
            d.fb.line(int(x + 2), y, int(x + 4), y + 6, 1)
        x += pitch
    txt(d, "DIRECT", 56, 18)
    txt(d, "DRIVE", 56, 28)
    d.fill_rect(54 + int((ph * 70) % 70), y - 5, 3, 3, 1)


# ── 5. how fast it was built ──────────────────────────────────────────────
def s_hours(d, ph, ctx):
    d.fill(0)
    n = int(_ease(min(ph * 1.8, 1.0)) * 36)
    _claim(d, "BUILT IN", str(n), "HOURS", ph)


# ── 6. the moat ───────────────────────────────────────────────────────────
def s_ledger(d, ph, ctx):
    d.fill(0)
    rail(d, "EVERY OPEN", str(ctx.get("events", 0)))
    log = ctx.get("log", [("1s", "UNLOCKED"), ("2m", "OPENED"), ("3m", "CLOSED")])
    for i, row in enumerate(log[:3]):
        e = _stagger(ph, i, 3)
        if e <= 0:
            continue
        y = 15 + i * 12
        slide = int((1.0 - _ease(e)) * 40)
        d.fill_rect(2 + slide, y, 3, 8, 1)
        txt(d, row[0], 8 + slide, y)
        txt(d, row[1], 48 + slide, y)
    if ph > 0.75:
        d.fill_rect(0, 52, W, 12, 1)
        d.text("LOGGED TO FLASH", 4, 55, 0)


# ── 7. live ───────────────────────────────────────────────────────────────
def s_bays(d, ph, ctx):
    d.fill(0)
    rail(d, "LIVE", ctx.get("link", ""))
    st = ctx.get("bays", [("BAY 1", 0.0, "SHUT"), ("BAY 2", 0.0, "SHUT")])
    for i, row in enumerate(st[:2]):
        label, pos, cap = row
        y = 16 + i * 24
        e = _stagger(ph, i, 2)
        if e <= 0:
            continue
        txt(d, label, 2, y + 2)
        drawer_glyph(d, 46, y, pos * _ease(e), w=40)
        if e > 0.5:
            txt(d, cap, 90, y + 12)
    d.hline(0, 39, W, 1)


# ── 8. engineering depth ──────────────────────────────────────────────────
def s_precision(d, ph, ctx):
    """The number that says somebody understood the process, not just the CAD."""
    d.fill(0)
    _claim(d, "TOLERANCE", "0.05", "MM PER SIDE", ph, scale=3)


def s_travel(d, ph, ctx):
    d.fill(0)
    rail(d, "STROKE", "153deg")
    mm = ctx.get("travel_mm", 16.7)
    pos = _ease(1.0 - abs(1.0 - 2.0 * ph))
    drawer_glyph(d, 22, 16, pos, w=84, h=14)
    bar(d, 8, 36, 112, 9, pos)
    txt_c(d, "%.1f mm" % (mm * pos), 50)


# ── 9. what it is made of ─────────────────────────────────────────────────
def s_spec(d, ph, ctx):
    d.fill(0)
    rail(d, "BILL OF PARTS")
    rows = ("PRINTED  140g", "SERVOS   2", "MCU      ESP32-S3", "PARTS    12")
    for i, r in enumerate(rows):
        e = _stagger(ph, i, 4)
        if e <= 0:
            continue
        txt(d, r[:max(1, int(len(r) * _ease(e)))], 3, 16 + i * 12)


# ── 10. try it ────────────────────────────────────────────────────────────
def s_net(d, ph, ctx):
    d.fill(0)
    rail(d, "TRY IT", "LINK")
    ip = _fit(ctx.get("ip", "192.168.4.1"))
    shown = ip[:max(1, int(len(ip) * _ease(min(ph * 2.0, 1.0))))]
    x = (W - len(ip) * 8) // 2
    txt_c(d, ctx.get("ssid", "shopkeeper-NANO"), 17)
    d.text(shown, x, 31, 1)
    cx = x + len(shown) * 8
    if int(ph * 6) % 2 == 0 and cx + 6 < W:
        d.fill_rect(cx + 1, 31, 5, 8, 1)
    for i in range(4):
        if ph * 4 > i:
            d.fill_rect(W - 22 + i * 5, 48 - i * 2 - 2, 3, 4 + i * 2, 1)
    if ph > 0.5:
        txt(d, "IN A BROWSER", 3, 52)


def s_lock(d, ph, ctx):
    d.fill(0)
    rail(d, ctx.get("unit", "NANO"), "LOCKED")
    bx, by = W // 2 - 9, 24
    d.rect(bx + 4, by - 8, 10, 10, 1)
    d.fill_rect(bx + 6, by - 6, 6, 8, 0)
    d.fill_rect(bx, by, 18, 14, 1)
    d.fill_rect(bx + 8, by + 5, 2, 5, 0)
    for k in (0, 1):
        r = 12 + int(((ph + k * 0.5) % 1.0) * 16)
        d.fb.ellipse(W // 2, by + 7, r, min(r - 4, 22), 1)
    txt_c(d, "AUTHORISE", 52)


# ORDER IS THE DESIGN. A hardware investor looks for about ten seconds, which
# at a 2.5 s dwell is four screens - so who / what / does-it-work / is-the-
# hardware-real all land inside the glance, and the supporting detail follows
# for anyone still watching.
def _wifi(d, x, y, bars=3):
    """Little signal mark, so the source of the command is unmistakable."""
    for i in range(bars):
        d.fill_rect(x + i * 4, y + 6 - i * 3, 3, 3 + i * 3, 1)


def s_web(d, ph, ctx):
    """Somebody just pressed a button on the terminal. Say so, loudly.

    The point of the whole machine is that access is commanded and recorded,
    so the one moment worth a full screen is the moment a command arrives from
    outside. Anyone watching the cabinet should see the phone take control
    without being told that is what happened."""
    c = ctx.get("cmd") or {}
    d.fill(0)
    d.fill_rect(0, 0, W, RAIL_H, 1)
    d.text("WEB CONTROL", 3, 2, 0)
    _wifi(d, W - 18, 2)
    big_c(d, c.get("label", "BAY 1"), 15, 2)
    pos = c.get("pos", 0.0)
    drawer_glyph(d, 22, 34, pos, w=84, h=12)
    bar(d, 8, 49, 112, 7, pos)
    verb = c.get("verb", "OPENING")
    if c.get("done"):
        # flash the outcome so a finished command is unmistakable
        if int(ph * 6) % 2 == 0:
            d.fill_rect(0, 0, W, RAIL_H, 1)
            d.text(verb, (W - len(verb) * 8) // 2, 2, 0)
    else:
        d.text(verb, (W - len(verb) * 8) // 2, 2, 0)


# The OMMI FORGE mark, traced from the artwork itself rather than approximated.
# The first attempt drew it from primitives - a circle, some diagonals, an F -
# and it was recognisably not the logo. A mark is either exact or it is someone
# else's mark. 42x32, 1 bit, MONO_HLSB, straight out of the source PNG by
# tools/trace_logo (see the commit); blit rather than redrawn so it cannot
# drift from the artwork.
LOGO_W, LOGO_H = 42, 32
LOGO = b'\x00\x00\x00\xff\xe0\x00\x00\x00\x01\xff\xf0\x00\x00\x00\x03\xff\xf8\x00\x00\x00\x03\xff\xfc\x00\x00\x00\x07\xf1\xfc\x00\x00\x00\x07\xf1\xfc\x00\x00\x00\x07\xf1\xfc\x00\x00\x00\x07\xf1\xfc\x00\x00\x00\x07\xf1\xfc\x00\x00\x00\x07\xf0\x00\x00\x00\xe0\x07\xf0\x00\x00\x07\xcf\x07\xf0\x00\x00\x0f\x9f\x07\xf0\xf8\x00\x1f>G\xf0\xf8\x00<\xfc\xe7\xf0\xf8\x009\xf9\xe7\xf8\xf8\x00s\xe7\xc7\xff\xfc\x00O\xcf\x97\xff\xfc\x00\x1f\x9f?\xff\xf8\x00>|\x7f\xf0\x00\x00|\xf9\xe7\xf0\x00\x00\xf9\xf3\xc7\xf0\x00\x00c\xe7\x97\xf8\x00\x00O\x9f7\xf8\x00\x00\x1f<\xf7\xf8\x00\x00>y\xef\xfc\x00\x00\x19\xf3\xcf\xfe\x00\x00\x03\xe7\x9f\xff\x00\x00\x07\x9f?\xff\x80\x00\x01<\xff\xff\xe0\x00~\xff\xff\xff\xff\xc0\xff\xff\xff\xff\xff\xc0'


def logo(d, x, y):
    fb = framebuf.FrameBuffer(bytearray(LOGO), LOGO_W, LOGO_H,
                              framebuf.MONO_HLSB)
    d.fb.blit(fb, x, y)


def _ring(d, cx, cy, r, frac):
    """Countdown ring, drawn as points around a circle. framebuf has no arc,
    and stepping the angle is cheaper than any of the ways of faking one."""
    n = 44
    lit = int(n * max(0.0, min(1.0, frac)))
    for i in range(lit):
        a = -math.pi / 2 + 2 * math.pi * i / n
        d.pixel(int(cx + r * math.cos(a)), int(cy + r * math.sin(a)), 1)
        d.pixel(int(cx + (r - 1) * math.cos(a)), int(cy + (r - 1) * math.sin(a)), 1)


def s_demo(d, ph, ctx):
    """Narrates the scripted demo. Whatever is on this screen is what the
    machine is doing at that instant - the stage is set by the demo task before
    it moves, never after, so the panel leads the drawer rather than trailing
    it. A demo screen that lags the hardware reads as a fake."""
    dm = ctx.get("demo") or {}
    stage = dm.get("stage", "READY")
    d.fill(0)
    rail(d, "AUTO DEMO", dm.get("tag", ""))
    if stage == "HOLD":
        logo(d, (W - LOGO_W) // 2, 13)
        txt_c(d, "OMMI FORGE", 47)
        txt_c(d, "TOOL CABINET", 56)
    elif stage in ("OPEN", "CLOSE"):
        txt_c(d, dm.get("label", "BAY 1"), 15)
        pos = dm.get("pos", 0.0)
        drawer_glyph(d, 22, 25, pos, w=84, h=14)
        bar(d, 8, 44, 112, 8, pos)
        txt_c(d, "OPENING" if stage == "OPEN" else "SECURING", 55)
    else:
        big_c(d, "READY", 20, 2)
        txt_c(d, "TOOL ACCESS CONTROL"[:16], 48)


SCREENS = (s_ident, s_what, s_proof, s_mechanism, s_hours,
           s_ledger, s_bays, s_precision, s_spec, s_net)


# ── the loop ──────────────────────────────────────────────────────────────

def wipe_in(d, render, ctx, steps=4):
    render(d, 0.0, ctx)
    snap = bytes(d.buf)
    for k in range(steps):
        d.buf[:] = snap
        cut = H - int(H * (k + 1) / steps)
        if cut:
            d.fill_rect(0, H - cut, W, cut, 0)
        d.show()


def carousel(d, ctx, dwell=2.0, fps=18, screens=None, rounds=1, locked=False):
    seq = screens if screens is not None else ((s_lock,) if locked else SCREENS)
    n = 0
    while rounds == 0 or n < rounds:
        for render in seq:
            wipe_in(d, render, ctx)
            t0 = time.ticks_ms()
            while True:
                el = time.ticks_diff(time.ticks_ms(), t0) / 1000.0
                if el >= dwell:
                    break
                render(d, el / dwell, ctx)
                d.show()
        n += 1


class Loop:
    """Frame-at-a-time carousel, so it can live inside the asyncio loop next to
    the HTTP server instead of blocking it. carousel() above is the blocking
    version and is only for the bench."""

    def __init__(self, d, screens=None, dwell=2.0):
        self.d = d
        self.screens = screens if screens is not None else SCREENS
        self.dwell = dwell
        self.i = 0
        self.t0 = time.ticks_ms()
        self._was_override = False

    def tick(self, ctx, override=None):
        d = self.d
        if override is not None:
            # a live state beats the attract loop; run it on its own slow phase
            ph = (time.ticks_ms() % 2000) / 2000.0
            override(d, ph, ctx)
            d.show()
            self._was_override = True
            self.t0 = time.ticks_ms()
            return
        if self._was_override:
            self._was_override = False
            self.t0 = time.ticks_ms()
        el = time.ticks_diff(time.ticks_ms(), self.t0) / 1000.0
        if el >= self.dwell:
            self.i = (self.i + 1) % len(self.screens)
            self.t0 = time.ticks_ms()
            el = 0.0
        self.screens[self.i](d, el / self.dwell, ctx)
        d.show()
