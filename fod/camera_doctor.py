#!/usr/bin/env python3
"""FOD Guard camera doctor — find the camera, find its snapshot URL, serve it.

One tool that answers "why is the camera not working" from the computer that
runs FOD Guard. Pure standard library; works on Windows / Linux / macOS.

USAGE
  1) Full check of a known camera (recommended):
       python3 fod/camera_doctor.py 192.168.0.128 admin PASSWORD
  2) Camera IP unknown / maybe changed? Scan the local network:
       python3 fod/camera_doctor.py --scan
  3) Once a snapshot works, keep this running and point the app at it:
       python3 fod/camera_doctor.py 192.168.0.128 admin PASSWORD --serve
     -> app camera snapshot URL:  http://localhost:8090/snapshot.jpg
     (served with CORS, re-fetched from the camera on every request)

WHAT IT CHECKS, IN ORDER
  network reachability (TCP 80/554) -> every common snapshot path, with
  Basic+Digest login -> saves camera_proof.jpg on success. Prints a report
  you can copy-paste when asking for help.
"""
import socket
import struct
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

SNAPSHOT_PATHS = [
    "/cgi-bin/snapshot.cgi",                       # CP Plus / Dahua
    "/cgi-bin/snapshot.cgi?channel=1",             # CP Plus / Dahua NVR channel
    "/ISAPI/Streaming/channels/101/picture",       # Hikvision
    "/Streaming/channels/1/picture",               # Hikvision (older)
    "/snapshot.jpg",                               # generic
    "/jpg/image.jpg",                              # Axis / generic
    "/webcapture.jpg?command=snap&channel=1",      # some DVRs
    "/tmpfs/auto.jpg",                             # some Chinese IPCs
    "/image/jpeg.cgi",                             # D-Link
]
SERVE_PORT = 8090


def tcp_open(ip, port, timeout=1.5):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def opener_for(user, password, url):
    if not user:
        return urllib.request.build_opener()
    mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, url, user, password or "")
    return urllib.request.build_opener(
        urllib.request.HTTPBasicAuthHandler(mgr),
        urllib.request.HTTPDigestAuthHandler(mgr),
    )


def try_snapshot(ip, path, user, password, timeout=6):
    url = f"http://{ip}{path}"
    try:
        resp = opener_for(user, password, url).open(url, timeout=timeout)
        data = resp.read()
        if data[:2] == b"\xff\xd8":
            return ("OK", url, data)
        ctype = resp.headers.get("Content-Type", "?")
        return (f"answered but not a JPEG (Content-Type: {ctype})", url, None)
    except urllib.error.HTTPError as e:
        return (f"HTTP {e.code}" + (" (login rejected)" if e.code in (401, 403) else ""), url, None)
    except Exception as e:
        return (str(e), url, None)


def local_subnet():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    base = struct.unpack(">I", socket.inet_aton(ip))[0] & 0xFFFFFF00
    return ip, [socket.inet_ntoa(struct.pack(">I", base + i)) for i in range(1, 255)]


def scan():
    me, hosts = local_subnet()
    print(f"This computer is {me} — scanning {hosts[0]}–{hosts[-1]} for web devices (port 80)…")
    found, lock, todo = [], threading.Lock(), list(hosts)

    def worker():
        while True:
            with lock:
                if not todo:
                    return
                ip = todo.pop()
            if tcp_open(ip, 80, 0.6):
                tag = ""
                try:
                    r = urllib.request.urlopen(f"http://{ip}/", timeout=2)
                    tag = (r.headers.get("Server", "") or "")[:40]
                except urllib.error.HTTPError as e:
                    tag = (e.headers.get("WWW-Authenticate", "") or e.headers.get("Server", "") or "")[:60]
                except Exception:
                    pass
                low = tag.lower()
                mark = " <-- looks like a camera/DVR" if any(
                    k in low for k in ("dahua", "hik", "ipc", "dvr", "nvr", "webs", "goahead", "login to")) else ""
                with lock:
                    found.append((ip, tag, mark))
                    print(f"  {ip:15s}  {tag}{mark}")

    threads = [threading.Thread(target=worker) for _ in range(48)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    if not found:
        print("No web devices found. The camera is off, on another network, or Wi-Fi dropped it.")
    else:
        print(f"\n{len(found)} device(s) answered. Re-run with the camera's IP and login:\n"
              f"  python3 fod/camera_doctor.py <ip> admin PASSWORD")
    return found


def doctor(ip, user, password):
    print(f"— Checking camera {ip} —")
    web, rtsp = tcp_open(ip, 80), tcp_open(ip, 554)
    print(f"  web port 80 : {'reachable' if web else 'NOT reachable'}")
    print(f"  rtsp port 554: {'open' if rtsp else 'closed'}")
    if not web and not rtsp:
        print("\nVERDICT: camera is unreachable at this IP — it is off, rebooting, or its IP changed.")
        print("Run  python3 fod/camera_doctor.py --scan  to find it, and give it a fixed IP")
        print("(DHCP reservation) in the router so this stops happening.")
        return None
    if not web:
        print("\nVERDICT: the camera talks RTSP video only (no web/JPEG service on port 80).")
        print("Enable its web service in the maker's app, take the snapshot from the DVR/NVR")
        print("instead, or use a USB capture dongle on a monitor output.")
        return None
    best = None
    print("  trying snapshot paths" + (f" as {user}" if user else " without login") + ":")
    for path in SNAPSHOT_PATHS:
        status, url, data = try_snapshot(ip, path, user, password)
        print(f"    {path:45s} {status}")
        if data and not best:
            best = (url, data)
    if best:
        url, data = best
        with open("camera_proof.jpg", "wb") as f:
            f.write(data)
        cred = f"{user}:{password}@" if user else ""
        full = url.replace("http://", f"http://{cred}", 1)
        print(f"\nVERDICT: WORKING — snapshot saved to camera_proof.jpg ({len(data)} bytes)")
        print("Use in FOD Guard either way:")
        print(f"  a) python3 fod/camera_doctor.py {ip} {user or ''} {'PASSWORD' if password else ''} --serve")
        print(f"     -> camera snapshot URL:  http://localhost:{SERVE_PORT}/snapshot.jpg")
        print(f"  b) python3 fod/snapshot_proxy.py   ->   http://localhost:{SERVE_PORT}/?u={full}")
        return full
    print("\nVERDICT: camera web answers but no snapshot path worked.")
    print("If every line says HTTP 401/403 -> the username/password is wrong.")
    print("Otherwise this model hides its snapshot path: check its manual/web UI,")
    print("or take the snapshot from the DVR/NVR it records to.")
    return None


def serve(camera_url):
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Snap(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                parts = urllib.parse.urlsplit(camera_url)
                user = password = None
                host = parts.netloc
                if "@" in host:
                    cred, host = host.rsplit("@", 1)
                    user, _, password = cred.partition(":")
                clean = urllib.parse.urlunsplit((parts.scheme, host, parts.path, parts.query, ""))
                data = opener_for(user, password, clean).open(clean, timeout=6).read()
            except Exception as e:
                self.send_error(502, f"camera fetch failed: {e}")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    print(f"\nServing the camera at  http://localhost:{SERVE_PORT}/snapshot.jpg  (Ctrl+C to stop)")
    print("Put that URL in FOD Guard as the camera snapshot URL.")
    HTTPServer(("127.0.0.1", SERVE_PORT), Snap).serve_forever()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--serve"]
    do_serve = "--serve" in sys.argv
    if not args or args[0] == "--scan":
        scan()
        sys.exit(0)
    ip = args[0]
    user = args[1] if len(args) > 1 else None
    password = args[2] if len(args) > 2 else None
    working = doctor(ip, user, password)
    if working and do_serve:
        serve(working)
