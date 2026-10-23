#!/usr/bin/env python3
"""FOD Guard home server — the whole setup in one command.

Run this on a computer that sits on the same network as the camera (a home
server, a spare PC). It does four things at once:

  1. checks the camera and finds its working snapshot path (camera_doctor),
  2. serves the FOD Guard app to every device on your network,
  3. serves the camera's picture at /snapshot.jpg on the SAME address —
     same origin as the app, so there is no CORS or mixed-content problem
     at all, and the camera login (Basic/Digest) is handled server-side,
  4. answers /scan — the app's "Scan network for cameras" button — with a
     JSON sweep of the subnet, and proxies ANY found camera at
     /snapshot.jpg?ip=<camera-ip> (same login for all), which is how one
     server supervises many machines in central mode.

USAGE (from the repo folder or anywhere):

    python3 fod/home_server.py 192.168.0.128 admin PASSWORD

Camera IP unknown? Start without it and use the app's scan button:

    python3 fod/home_server.py - admin PASSWORD

Then, from ANY device on the network, open the address it prints, e.g.

    http://192.168.0.42:8000/fod/index.html

The app detects /snapshot.jpg and configures itself.
Pure standard library; works on Windows / Linux / macOS.
"""
import ipaddress
import json
import os
import socket
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import camera_doctor as cd  # reuses doctor's auth + path-probing logic

PORT = int(os.environ.get("FOD_PORT", "8000"))


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Run:  python3 fod/home_server.py <camera-ip> [user] [password]")
        print("Camera IP unknown?  python3 fod/home_server.py - [user] [password]")
        print("then press 'Scan network for cameras' in the app's Settings.")
        sys.exit(1)
    ip = sys.argv[1]
    user = sys.argv[2] if len(sys.argv) > 2 else None
    password = sys.argv[3] if len(sys.argv) > 3 else None

    camera_url = None
    if ip != "-":
        camera_url = cd.doctor(ip, user, password)  # prints its own report
        if not camera_url:
            print("\nFix the camera per the verdict above, then run this again.")
            sys.exit(2)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)

    snap_cache = {}            # camera ip -> working credential-free snapshot URL
    cache_lock = threading.Lock()

    def lan_addr(s):
        try:
            a = ipaddress.ip_address(s)
        except ValueError:
            return False
        return a.version == 4 and (a.is_private or a.is_loopback)

    def probe(cam_ip):
        """Find (and cache) the working snapshot URL for a camera on the LAN."""
        with cache_lock:
            if cam_ip in snap_cache:
                return snap_cache[cam_ip]
        for path in cd.SNAPSHOT_PATHS:
            status, url, _ = cd.try_snapshot(cam_ip, path, user, password, timeout=4)
            if status == "OK":
                with cache_lock:
                    snap_cache[cam_ip] = url
                return url
        return None

    class App(SimpleHTTPRequestHandler):
        def do_GET(self):
            route = self.path.split("?")[0]
            if route == "/scan":
                return self.handle_scan()
            if route == "/snapshot.jpg":
                return self.handle_snapshot()
            super().do_GET()

        def handle_scan(self):
            qs = cd.urllib.parse.parse_qs(cd.urllib.parse.urlsplit(self.path).query)
            net = (qs.get("net") or [None])[0]
            if net:
                probe = ".".join((net.split(".") + ["0", "0", "0"])[:3]) + ".0"
                if not lan_addr(probe):
                    self.send_error(400, "net must be a local-network IPv4 subnet, e.g. 192.168.1")
                    return
            found = cd.scan(net=net)  # prints progress to the server console too
            body = json.dumps([
                {"ip": f_ip, "tag": tag, "camera": bool(mark)}
                for f_ip, tag, mark in sorted(found)
            ]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def handle_snapshot(self):
            qs = cd.urllib.parse.parse_qs(cd.urllib.parse.urlsplit(self.path).query)
            want_ip = (qs.get("ip") or [None])[0]
            u, p = user, password
            if want_ip:
                if not lan_addr(want_ip):
                    self.send_error(400, "ip must be a local-network IPv4 address")
                    return
                url = probe(want_ip)
                if not url:
                    self.send_error(502, f"no snapshot endpoint answered at {want_ip} "
                                         "(check the camera and that it uses the same login)")
                    return
            elif camera_url:
                parts = cd.urllib.parse.urlsplit(camera_url)
                host = parts.netloc
                if "@" in host:
                    cred, host = host.rsplit("@", 1)
                    u, _, p = cred.partition(":")
                url = cd.urllib.parse.urlunsplit(
                    (parts.scheme, host, parts.path, parts.query, ""))
            else:
                self.send_error(404, "no camera configured at launch — use /snapshot.jpg?ip=<camera-ip> "
                                     "or press 'Scan network for cameras' in the app")
                return
            try:
                data = cd.opener_for(u, p, url).open(url, timeout=6).read()
            except Exception as e:
                self.send_error(502, f"camera fetch failed: {e}")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    me = lan_ip()
    print("\n" + "=" * 62)
    print("FOD GUARD HOME SERVER IS RUNNING  (Ctrl+C to stop)")
    print("  On any device on this network, open:")
    print(f"      http://{me}:{PORT}/fod/index.html")
    if camera_url:
        print("  The app will connect the camera automatically (/snapshot.jpg).")
    else:
        print("  No camera given — press 'Scan network for cameras' in Settings.")
    print("  More machines: per-job camera URL  /snapshot.jpg?ip=<camera-ip>")
    print("=" * 62)
    ThreadingHTTPServer(("0.0.0.0", PORT), App).serve_forever()


if __name__ == "__main__":
    main()
