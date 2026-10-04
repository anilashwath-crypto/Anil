#!/usr/bin/env python3
"""FOD Guard snapshot proxy.

Most IP cameras/DVRs (CP Plus, Hikvision, Dahua...) serve a JPEG snapshot but
without the CORS header a browser needs to let a web page READ its pixels —
the live picture displays fine, yet "Capture master" / cycle checks fail with
a CORS or tainted-canvas error. Many of them also require HTTP digest
authentication, which a browser fetch cannot do cross-origin at all. This
proxy fetches the JPEG server-side (handling Basic and Digest auth) and
re-serves it with Access-Control-Allow-Origin, which fixes both problems.

Run on the computer whose browser runs FOD Guard:

    python3 fod/snapshot_proxy.py

Then use this as the camera snapshot URL in the app (Settings, or a job's
Central-mode field), with your camera's real snapshot URL after ?u= —
credentials go inside that URL as user:password@host :

    http://localhost:8090/?u=http://admin:PASSWORD@192.168.1.64/cgi-bin/snapshot.cgi

Tip: first make sure the camera URL itself shows a photo when opened in a
browser tab (the browser will ask for the login). Common snapshot paths:
CP Plus / Dahua: /cgi-bin/snapshot.cgi (add ?channel=1 for NVR channels),
Hikvision: /ISAPI/Streaming/channels/101/picture — check your model's manual.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, urlsplit, urlunsplit, unquote
import urllib.request
import urllib.error

PORT = 8090


def fetch_camera(url):
    """GET the camera URL, handling user:password@ credentials (Basic+Digest)."""
    parts = urlsplit(url)
    if "@" in parts.netloc:
        creds, host = parts.netloc.rsplit("@", 1)
        user, _, password = creds.partition(":")
        clean = urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
        mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        mgr.add_password(None, clean, unquote(user), unquote(password))
        opener = urllib.request.build_opener(
            urllib.request.HTTPBasicAuthHandler(mgr),
            urllib.request.HTTPDigestAuthHandler(mgr),
        )
        return opener.open(clean, timeout=6)
    return urllib.request.urlopen(url, timeout=6)


class Snap(BaseHTTPRequestHandler):
    def do_GET(self):
        url = parse_qs(urlparse(self.path).query).get("u", [None])[0]
        if not url or not url.startswith(("http://", "https://")):
            self.send_error(400, "pass the camera snapshot URL as ?u=http://...")
            return
        try:
            resp = fetch_camera(url)
            data = resp.read()
            ctype = resp.headers.get("Content-Type", "image/jpeg")
        except urllib.error.HTTPError as e:
            print(f"[proxy] camera answered HTTP {e.code} for {url}")
            self.send_error(502, f"camera answered HTTP {e.code} "
                                 "(401/403 = wrong or missing user:password@ in the ?u= URL)")
            return
        except Exception as e:
            print(f"[proxy] camera fetch failed for {url}: {e}")
            self.send_error(502, f"camera fetch failed: {e}")
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # keep the terminal quiet on success
        pass


if __name__ == "__main__":
    print(f"FOD Guard snapshot proxy on http://localhost:{PORT}/?u=<camera-jpeg-url>")
    print("Credentials go inside the ?u= URL:  ?u=http://admin:PASSWORD@192.168.1.64/cgi-bin/snapshot.cgi")
    HTTPServer(("127.0.0.1", PORT), Snap).serve_forever()
