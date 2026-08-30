#!/usr/bin/env python3
"""HouseKeeper local hub — The House Of Ommi.

Serves the app to every phone on your home WiFi while development continues.

Run it on the computer that stays at home:
    python3 hub.py          (Mac/Linux)
    py hub.py               (Windows, with Python from python.org)

Then on each phone (same WiFi), open the "On phones" address it prints and
use the browser menu -> Add to Home screen.

Notes
-----
* Each phone keeps its own data (the app stores everything on-device).
  Move data between phones with More -> Export/Import backup.
* The app lock (password / face unlock) needs https or localhost, so on the
  plain hub address the app runs unlocked — the lock activates on the GitHub
  Pages site after the branch is merged.
* Optional — public https tunnel with ngrok (https://ngrok.com, free account):
      ngrok http 8080
  gives a temporary https://xxxx.ngrok-free.app URL that works from anywhere
  (not just your WiFi) AND enables the app lock + face unlock, because it is
  https. The URL changes each run; treat it as a development preview.
* Stop the hub with Ctrl+C.
"""
import http.server
import os
import socket
import socketserver

PORT = 8080

os.chdir(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # always serve the latest edit while the app is under development
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):  # quieter console
        pass


def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print("HouseKeeper hub is running — The House Of Ommi")
    print(f"  On this computer:      http://localhost:{PORT}")
    for ip in lan_ips() or ["<this-computer's-IP>"]:
        print(f"  On phones (same WiFi): http://{ip}:{PORT}")
    print("Press Ctrl+C to stop.")
    httpd.serve_forever()
