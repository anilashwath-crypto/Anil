"""
shopkeeper NANO — entry point.

Brings up the network, restores calibration, starts the servos in the closed
position and serves the UI. Written so that a failure anywhere still leaves a
reachable cabinet: if the wifi join fails it falls back to its own AP, and if
the AP fails too it keeps serving on whatever interface came up.
"""
try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

import gc
import network
import time

import config
import store
from servo import Servo
from server import App, serve

try:
    import sh1106
    import hud
except ImportError:      # a cabinet with no screen is still a cabinet
    sh1106 = hud = None


def _banner(*rows):
    # str.ljust does not exist in MicroPython - pad by hand
    w = max(len(r) for r in rows)
    print("+" + "-" * (w + 2) + "+")
    for r in rows:
        print("| " + r + " " * (w - len(r)) + " |")
    print("+" + "-" * (w + 2) + "+")


def bring_up_network():
    """Returns (mode, ip). Tries to join a known network first if one is
    configured, because a cabinet on the shop wifi is reachable from a laptop
    that also needs the internet. Falls back to its own AP, which is what
    actually gets used in a meeting room."""
    if config.JOIN:
        ssid, pw = config.JOIN
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        if not sta.isconnected():
            sta.connect(ssid, pw)
            t0 = time.ticks_ms()
            while not sta.isconnected():
                if time.ticks_diff(time.ticks_ms(), t0) > config.JOIN_TIMEOUT_S * 1000:
                    break
                time.sleep_ms(200)
        if sta.isconnected():
            return "STA:" + ssid, sta.ifconfig()[0]
        sta.active(False)

    if not config.AP_PASSWORD or len(config.AP_PASSWORD) < 8:
        # Refuse rather than fall through to an open AP next to the drawers.
        raise RuntimeError("set AP_PASSWORD (8+ chars) in firmware/secrets.py")
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    try:
        ap.config(essid=config.AP_SSID, password=config.AP_PASSWORD,
                  authmode=network.AUTH_WPA_WPA2_PSK)
    except Exception:
        ap.config(essid=config.AP_SSID)          # open, if WPA is refused
    t0 = time.ticks_ms()
    while not ap.active() and time.ticks_diff(time.ticks_ms(), t0) < 4000:
        time.sleep_ms(100)
    return "AP:" + config.AP_SSID, ap.ifconfig()[0]


async def _housekeeping(app):
    """One place that owns the slow, boring, must-not-be-forgotten work."""
    while True:
        await asyncio.sleep(5)
        app.log.maybe_flush()
        gc.collect()


def _hms(sec):
    sec = int(sec)
    if sec < 60:
        return str(sec) + "s"
    if sec < 3600:
        return "%dm %02ds" % (sec // 60, sec % 60)
    return "%dh %02dm" % (sec // 3600, (sec % 3600) // 60)


def _hud_ctx(app, ip, mode):
    """The same numbers the web terminal serves, shaped for a 128x64 panel.

    Read off app/servo state rather than kept in parallel - a display that
    disagrees with the page it sits next to is worse than no display."""
    ds = [d.state() for d in app.drawers]
    ev = app.log.entries
    up = time.time() - app.boot_at
    return {
        "unit": "SK-N-0001",
        "link": mode.split(":")[0] if mode else "-",
        "ssid": config.AP_SSID,
        "ip": ip,
        "cycles": sum(x["cycles"] for x in ds),
        "uptime": _hms(up),
        "heap": str(gc.mem_free() // 1024) + "K",
        "tools": len(getattr(config, "TOOLS", ()) or ()) or 8,
        "events": len(ev),
        "travel_mm": ds[0]["travel_mm"] if ds else 16.7,
        "bays": [("BAY " + str(i + 1), x["pos"],
                  "OPEN" if x["open"] else "SHUT") for i, x in enumerate(ds)],
        "log": [(_hms(max(0, up - e.get("up", up))), e.get("what", "")[:8])
                for e in ev[:3]],
        "test_cycles": getattr(config, "TEST_CYCLES", 0),
        "test_fail": getattr(config, "TEST_FAILURES", 0),
        "moving_label": "BAY 1",
        "moving_pos": 0.0,
    }


async def _demo(app):
    """The unattended performance: hold a card, open bay one, open bay two,
    secure both, hand back to the attract loop.

    app.demo is set BEFORE each move and cleared after, so the panel always
    leads the hardware. It drives the servos through the same Servo.move() the
    HTTP handler uses and writes the same log entries, so a demo open is a real
    open - the ledger does not get a special case it can lie in."""
    await asyncio.sleep(2)
    while True:
        # Stand down while a person is driving. Two things moving the same
        # drawer for different reasons is how a demo embarrasses you.
        # Also stand down while the control page has switched the demo off.
        while getattr(app, "cmd", None) or not app.demo_on:
            app.demo = None
            await asyncio.sleep_ms(300)
        t0 = time.time()
        while True:
            if getattr(app, "cmd", None) or not app.demo_on:
                break                                # somebody took over
            left = config.DEMO_HOLD_S - (time.time() - t0)
            if left <= 0:
                break
            app.demo = {"stage": "HOLD", "left": left + 1,
                        "frac": 1.0 - left / config.DEMO_HOLD_S,
                        "tag": "%ds" % int(left + 1)}
            await asyncio.sleep_ms(200)

        if getattr(app, "cmd", None) or not app.demo_on:
            continue                                  # never start a move we were told not to
        for i, dr in enumerate(app.drawers):          # open one, then the other
            app.demo = {"stage": "OPEN", "label": "BAY " + str(i + 1),
                        "pos": dr.pos, "tag": "%d/%d" % (i + 1, len(app.drawers))}
            await dr.move(True)
            app.log.add("OPENED", dr.id, "demo")
            app.demo = {"stage": "OPEN", "label": "BAY " + str(i + 1),
                        "pos": 1.0, "tag": "OPEN"}
            await asyncio.sleep(config.DEMO_DWELL_S)

        for i, dr in enumerate(app.drawers):          # then put it all back
            app.demo = {"stage": "CLOSE", "label": "BAY " + str(i + 1),
                        "pos": dr.pos, "tag": "SECURE"}
            await dr.move(False)
            app.log.add("CLOSED", dr.id, "demo")
            app.demo = {"stage": "CLOSE", "label": "BAY " + str(i + 1),
                        "pos": 0.0, "tag": "SECURE"}
            await asyncio.sleep(1)

        app.demo = None
        if not config.DEMO_LOOP:
            return
        await asyncio.sleep(config.DEMO_GAP_S)        # attract loop takes over


async def _display(app, d, ip, mode):
    """Runs forever. Never stops, never blanks.

    The first version wrapped the whole loop in one try/except and called
    poweroff() on the way out - so a single bad frame killed the panel until
    the next reboot, which is exactly the "goes black after a while" symptom.
    A display task that can die is worse than no display task: the cabinet
    looks broken while working perfectly.

    Now each frame is guarded on its own, a run of failures re-attaches the
    panel rather than giving up, and there is no code path that turns it off.
    The module browns out and latches under load - see sh1106.py - so losing
    it for a few seconds is normal and recovery has to be automatic."""
    loop = hud.Loop(d, dwell=config.OLED_DWELL)
    fails = 0
    while True:
        try:
            ctx = _hud_ctx(app, ip, mode)
            ctx["demo"] = getattr(app, "demo", None)
            # PRIORITY. A person pressing a button beats everything the
            # cabinet does of its own accord - including the scripted demo.
            # Whatever is on the panel, a web command takes it over at once and
            # holds it until the move finishes plus four seconds, so the
            # outcome is seen and not just the motion.
            #   web command  >  scripted demo  >  moving  >  locked  >  attract
            cmd = getattr(app, "cmd", None)
            if cmd:
                live = [sv for sv in app.drawers if sv.id == cmd.get("id")]
                if live and live[0].busy:
                    cmd["pos"] = live[0].pos
                if (not cmd.get("done")) or (time.time() - cmd.get("at", 0)) < 4:
                    ctx["cmd"] = cmd
                    loop.tick(ctx, hud.s_web)
                    fails = 0
                    await asyncio.sleep_ms(50)
                    continue
                app.cmd = None
            if ctx["demo"]:
                loop.tick(ctx, hud.s_demo)          # the script owns it next
                fails = 0
                await asyncio.sleep_ms(60)
                continue
            over = None
            for i, x in enumerate([sv.state() for sv in app.drawers]):
                if x["busy"]:
                    ctx["moving_label"] = "BAY " + str(i + 1)
                    ctx["moving_pos"] = x["pos"]
                    over = hud.s_moving
                    break
            if over is None and app.locked:
                over = hud.s_lock
            loop.tick(ctx, over)
            fails = 0
            await asyncio.sleep_ms(40 if over else 90)
        except Exception as e:
            fails += 1
            if fails in (1, 25):
                print("display hiccup (%d):" % fails, e)
            if fails >= 25:
                # the panel has probably browned out and latched; rebuild it
                try:
                    nd = sh1106.attach()
                    if nd:
                        d = nd
                        loop = hud.Loop(d, dwell=config.OLED_DWELL)
                        fails = 0
                        print("display re-attached")
                except Exception:
                    pass
            await asyncio.sleep_ms(400)


async def _amain():
    mode, ip = bring_up_network()

    # Attach the display BEFORE anything moves. Parking the drawers is the
    # peak current draw of the machine, and scanning for the panel during it
    # finds nothing.
    disp = sh1106.attach() if sh1106 else None

    drawers = [Servo(spec) for spec in config.DRAWERS]
    store.load_timing()          # live-edited stroke timing overrides config.py
    cal = store.load_cal()
    for d in drawers:
        got = cal.get(str(d.id))
        if got:
            d.calibrate(got[0], got[1])

    # Park closed at boot. The drawers may well be sitting open from last time,
    # and a cabinet whose UI says CLOSED while the drawer is out is worse than
    # one that moves unexpectedly on power-up.
    for d in drawers:
        await d.move(False, ms=700)

    log = store.Log()
    log.add("BOOT", None, mode)
    app = App(drawers, log)
    app.net = mode

    await serve(app)
    asyncio.create_task(_housekeeping(app))
    if getattr(config, "DEMO", False):
        asyncio.create_task(_demo(app))
        print("demo: scripted, %ds hold then both bays" % config.DEMO_HOLD_S)

    if disp:
        # Boot card. Uses SCREENS[0] rather than naming a screen: the set gets
        # reordered and renamed as the pitch changes, and a stale name here
        # crashes main and leaves the cabinet at a REPL prompt with no server.
        hud.SCREENS[0](disp, 1.0, {"link": mode.split(":")[0]})
        disp.show()
        asyncio.create_task(_display(app, disp, ip, mode))
        print("display: SH1106 on SCL%d/SDA%d" % (config.OLED_SCL, config.OLED_SDA))
    else:
        print("display: none")

    _banner("shopkeeper NANO",
            "net    " + mode,
            "open   http://" + ip + "/",
            "pin    " + ("*" * len(str(config.PIN))),
            "free   {} bytes".format(gc.mem_free()))

    while True:
        await asyncio.sleep(3600)


def run():
    try:
        asyncio.run(_amain())
    finally:
        asyncio.new_event_loop()


run()
