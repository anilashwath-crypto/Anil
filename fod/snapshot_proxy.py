#!/usr/bin/env python3
"""FOD Guard snapshot proxy.

Most IP cameras/DVRs (CP Plus, Hikvision, Dahua...) serve a JPEG snapshot but
without the CORS header a browser needs to let a web page READ its pixels —
the live picture displays fine, yet "Capture master" / cycle checks fail with
a CORS or tainted-canvas error. This proxy fetches the JPEG server-side and
re-serves it with Access-Control-Allow-Origin, which fixes that.

Run on the computer that runs FOD Guard:

    python3 fod/snapshot_proxy.py

Then use this as the camera snapshot URL in the app (Settings, or a job's
Central-mode field), with your camera's real snapshot URL after ?u= :

    http://localhost:8090/?u=http://192.168.1.64/cgi-bin/snapshot.cgi

Tip: the ?u= URL must return a raw JPEG when opened directly in a browser
tab — include credentials if the camera needs them, e.g.
...snapshot.cgi?chn=0&u=admin&p=PASSWORD (check your camera's manual).
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import urllib.request

PORT = 8090

class Snap(BaseHTTPRequestHandler):
    def do_GET(self):
        url = parse_qs(urlparse(self.path).query).get("u", [None])[0]
        if not url or not url.startswith(("http://", "https://")):
            self.send_error(400, "pass the camera snapshot URL as ?u=http://...")
            return
        try:
            data = urllib.request.urlopen(url, timeout=5).read()
        except Exception as e:
            self.send_error(502, f"camera fetch failed: {e}")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # keep the terminal quiet
        pass

if __name__ == "__main__":
    print(f"FOD Guard snapshot proxy on http://localhost:{PORT}/?u=<camera-jpeg-url>")
    HTTPServer(("127.0.0.1", PORT), Snap).serve_forever()
