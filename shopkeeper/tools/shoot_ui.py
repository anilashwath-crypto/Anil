#!/usr/bin/env python3
"""
Screenshots of the operator terminal, taken against the real www/index.html.

Served by firmware/mock_server.py, which imports the real firmware/config.py -
so the tool register, PIN, timeouts and servo endpoints on screen are the ones
the hardware runs, not a mock-up of them.

Headless Chromium via Playwright rather than macOS screencapture, which needs
Screen Recording permission this terminal does not have, and which would grab
whatever else is on the display.
"""
import json, os, sys, time, urllib.request
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "docs/img")
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8732"
os.makedirs(OUT, exist_ok=True)


def post(path, obj):
    rq = urllib.request.Request(BASE + path, data=json.dumps(obj).encode(),
                                headers={"Content-Type": "application/json"},
                                method="POST")
    try:
        with urllib.request.urlopen(rq, timeout=6) as r:
            return r.status
    except Exception as e:
        return str(e)


SHOTS = [
    # name, viewport, device_scale, before()
    ("ui_terminal.png", (1440, 980), 2, None),
    ("ui_locked.png",   (1440, 980), 2, "lock"),
    ("ui_mobile.png",   (414, 896),  3, None),
]


def main():
    errors = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for name, (w, h), scale, pre in SHOTS:
            if pre == "lock":
                post("/api/lock", {})
            else:
                post("/api/unlock", {"pin": "2468"})
            pg = b.new_page(viewport={"width": w, "height": h},
                            device_scale_factor=scale)
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console", lambda m: errors.append(m.text)
                  if m.type == "error" else None)
            pg.goto(BASE, wait_until="networkidle", timeout=20000)
            pg.wait_for_timeout(1400)          # let the first poll land
            p = os.path.join(OUT, name)
            pg.screenshot(path=p, full_page=(name != "ui_mobile.png"))
            print(f"  {name:20s} {w}x{h} @{scale}x   "
                  f"{os.path.getsize(p)/1024:.0f} KB")
            pg.close()
        b.close()
    # a screenshot of a broken page is worse than no screenshot
    print(f"\n  console/page errors: {len(errors)}")
    for e in errors[:8]:
        print(f"    {e[:120]}")


if __name__ == "__main__":
    main()
