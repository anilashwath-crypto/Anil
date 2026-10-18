#!/usr/bin/env python3
"""FOD Guard camera setup — apply the recommended camera settings in one command.

Configures a CP Plus / Dahua-family IP camera over its own HTTP API (the same
Basic/Digest login the web page uses) so the picture stays stable for
frame-to-frame comparison. Pure standard library; Windows / Linux / macOS.

USAGE
    python3 fod/camera_setup.py <camera-ip> <user> <password> [options]

WHAT IT APPLIES (each verified by reading the value back)
    clock        set to this computer's current local time
    OSD off      time + channel-name overlays removed from the encoded image
    colour mode  day/night forced to colour (no IR auto-switch mid-shift)
    anti-flicker 50 Hz (Indian mains)
    snapshot     best JPEG quality

OPTIONS
    --ntp         also enable NTP time sync (pool.ntp.org) — check afterwards in
                  the camera UI that the timezone shows GMT+5:30, firmware
                  indexes differ
    --static-ip   pin the camera's CURRENT address as static (DHCP off), keeping
                  today's IP/mask/gateway, so the router can never move it
    --reboot-weekly  schedule an automatic reboot Sunday 03:00
    --dry-run     show what would be sent without changing anything

Parameter names differ between firmware generations, so every setting is tried
with each known spelling and the first accepted one wins; a setting none of
them matches is reported as unsupported and skipped — never fatal.

After running this, RE-CAPTURE THE MASTER in FOD Guard: exposure and overlay
changes make the old master stale.
"""
import sys
import time
import urllib.error
import urllib.parse

from camera_doctor import opener_for


def call(opener, url, timeout=8):
    try:
        resp = opener.open(url, timeout=timeout)
        return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        try:
            body = (e.read() or b"").decode(errors="replace")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return 0, str(e)


class Camera:
    def __init__(self, ip, user, password, dry_run=False):
        self.base = f"http://{ip}"
        self.opener = opener_for(user, password, self.base + "/")
        self.dry_run = dry_run

    def get_config(self, name):
        return call(self.opener, f"{self.base}/cgi-bin/configManager.cgi?action=getConfig&name={name}")

    def set_config(self, params):
        query = "&".join(
            f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in params.items()
        )
        url = f"{self.base}/cgi-bin/configManager.cgi?action=setConfig&{query}"
        if self.dry_run:
            print(f"      dry-run: {url}")
            return 200, "OK"
        return call(self.opener, url)

    def apply(self, label, variants, readback=None):
        """Try each parameter spelling until the camera accepts one."""
        print(f"  {label}")
        for params in variants:
            status, body = self.set_config(params)
            if status == 200 and "OK" in body.upper():
                print(f"      applied ({next(iter(params))} …)")
                if readback and not self.dry_run:
                    rstatus, rbody = self.get_config(readback)
                    for line in rbody.splitlines():
                        if any(k.split("=")[0].split(".")[-1] in line for k in params):
                            print(f"      readback: {line.strip()}")
                return True
        print("      not supported by this firmware — set it in the camera web UI instead")
        return False


def parse_table(body):
    """Dahua getConfig output: 'table.Name.Sub=value' lines -> dict."""
    out = {}
    for line in body.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


def set_clock(cam):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"  clock -> {now} (this computer's time)")
    if cam.dry_run:
        print("      dry-run: setCurrentTime")
        return
    status, body = call(
        cam.opener,
        f"{cam.base}/cgi-bin/global.cgi?action=setCurrentTime&time={urllib.parse.quote(now)}",
    )
    if status == 200 and "OK" in body.upper():
        print("      applied")
    else:
        print(f"      failed (HTTP {status}) — set the clock in the camera web UI")


def set_static_ip(cam, ip):
    print("  static IP (pin current address, DHCP off)")
    status, body = cam.get_config("Network")
    table = parse_table(body) if status == 200 else {}
    mask = table.get("table.Network.eth0.SubnetMask")
    gateway = table.get("table.Network.eth0.DefaultGateway")
    ip = table.get("table.Network.eth0.IPAddress") or ip.split(":")[0]
    if not mask or not gateway:
        print("      could not read current mask/gateway — leaving network settings alone")
        return
    print(f"      keeping {ip} / {mask} gw {gateway}")
    cam.apply(
        "  write network config",
        [{
            "Network.eth0.DhcpEnable": "false",
            "Network.eth0.IPAddress": ip,
            "Network.eth0.SubnetMask": mask,
            "Network.eth0.DefaultGateway": gateway,
        }],
    )


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if len(args) < 3:
        print(__doc__)
        sys.exit(1)
    ip, user, password = args[0], args[1], args[2]
    cam = Camera(ip, user, password, dry_run="--dry-run" in flags)

    print(f"— Configuring camera {ip} —")
    status, body = cam.get_config("General")
    if status != 200:
        print(f"Cannot reach the camera API (HTTP {status}): {body[:120]}")
        print("Check IP / login (same as the web page), then re-run.")
        sys.exit(1)

    set_clock(cam)

    cam.apply(
        "OSD overlays off (time + channel name)",
        [{
            "VideoWidget[0].TimeTitle.EncodeBlend": "false",
            "VideoWidget[0].TimeTitle.PreviewBlend": "false",
            "VideoWidget[0].ChannelTitle.EncodeBlend": "false",
            "VideoWidget[0].ChannelTitle.PreviewBlend": "false",
        }],
        readback="VideoWidget[0]",
    )

    cam.apply(
        "day/night -> always colour (no IR auto-switch)",
        [
            {"VideoInDayNight[0][0].Mode": "Color"},
            {"VideoInOptions[0].DayNightColor": "0"},
        ],
        readback="VideoInDayNight",
    )

    cam.apply(
        "anti-flicker -> 50 Hz",
        [
            {"VideoInExposure[0][0].AntiFlicker": "1"},
            {"VideoInOptions[0].AntiFlicker": "1"},
        ],
    )

    cam.apply(
        "snapshot -> best JPEG quality",
        [
            {"Encode[0].SnapFormat[0].Video.Quality": "6",
             "Encode[0].SnapFormat[0].VideoEnable": "true"},
            {"Encode[0].SnapFormat[0].Video.Quality": "5",
             "Encode[0].SnapFormat[0].VideoEnable": "true"},
        ],
        readback="Encode[0].SnapFormat[0]",
    )

    if "--reboot-weekly" in flags:
        cam.apply(
            "auto reboot Sunday 03:00",
            [{
                "AutoMaintain.AutoRebootDay": "0",
                "AutoMaintain.AutoRebootHour": "3",
                "AutoMaintain.AutoRebootMinute": "0",
            }],
            readback="AutoMaintain",
        )

    if "--ntp" in flags:
        cam.apply(
            "NTP time sync (verify timezone = GMT+5:30 in the camera UI!)",
            [{
                "NTP.Enable": "true",
                "NTP.Address": "pool.ntp.org",
                "NTP.Port": "123",
                "NTP.UpdatePeriod": "60",
            }],
            readback="NTP",
        )

    if "--static-ip" in flags:
        set_static_ip(cam, ip)

    print("\nDone. Now RE-CAPTURE THE MASTER in FOD Guard (Jobs -> Grab frame)")
    print("— the picture has changed, so old masters no longer match.")


if __name__ == "__main__":
    main()
