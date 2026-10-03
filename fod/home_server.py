#!/usr/bin/env python3
"""FOD Guard home server — the whole setup in one command.

Run this on a computer that sits on the same network as the camera (a home
server, a spare PC). It does three things at once:

  1. checks the camera and finds its working snapshot path (camera_doctor),
  2. serves the FOD Guard app to every device on your network,
  3. serves the camera's picture at /snapshot.jpg on the SAME address —
     same origin as the app, so there is no CORS or mixed-content problem
     at all, and the camera login (Basic/Digest) is handled server-side.

USAGE (from the repo folder or anywhere):

    python3 fod/home_server.py 192.168.0.128 admin PASSWORD

Then, from ANY device on the network, open the address it prints, e.g.

    http://192.168.0.42:8000/fod/index.html

and in the app set the camera snapshot URL to simply:

    /snapshot.jpg

Pure standard library; works on Windows / Linux / macOS.
"""
import os
import socket
import sys
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
        print("Camera IP missing. Run:  python3 fod/home_server.py <camera-ip> [user] [password]")
        print("Camera IP unknown?  python3 fod/camera_doctor.py --scan")
        sys.exit(1)
    ip = sys.argv[1]
    user = sys.argv[2] if len(sys.argv) > 2 else None
    password = sys.argv[3] if len(sys.argv) > 3 else None

    camera_url = cd.doctor(ip, user, password)  # prints its own report
    if not camera_url:
        print("\nFix the camera per the verdict above, then run this again.")
        sys.exit(2)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)

    class App(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] == "/snapshot.jpg":
                parts = cd.urllib.parse.urlsplit(camera_url)
                u = p = None
                host = parts.netloc
                if "@" in host:
                    cred, host = host.rsplit("@", 1)
                    u, _, p = cred.partition(":")
                clean = cd.urllib.parse.urlunsplit(
                    (parts.scheme, host, parts.path, parts.query, ""))
                try:
                    data = cd.opener_for(u, p, clean).open(clean, timeout=6).read()
                except Exception as e:
                    self.send_error(502, f"camera fetch failed: {e}")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            super().do_GET()

        def log_message(self, *a):
            pass

    me = lan_ip()
    print("\n" + "=" * 62)
    print("FOD GUARD HOME SERVER IS RUNNING  (Ctrl+C to stop)")
    print(f"  On any device on this network, open:")
    print(f"      http://{me}:{PORT}/fod/index.html")
    print(f"  In the app, set the camera snapshot URL to:")
    print(f"      /snapshot.jpg")
    print("=" * 62)
    ThreadingHTTPServer(("0.0.0.0", PORT), App).serve_forever()


if __name__ == "__main__":
    main()
