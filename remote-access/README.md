# Remote access with RustDesk

[RustDesk](https://rustdesk.com) is a free, open-source remote desktop app, a
TeamViewer/AnyDesk alternative. Use it to look after the FOD Guard central
PC, the farm office PC, or a home laptop from your phone.

## 1. Your phone or laptop (the one you control *from*)

| Device | Get it |
|---|---|
| Android | Play Store → **RustDesk Remote Desktop** (or the `.apk` on [GitHub releases](https://github.com/rustdesk/rustdesk/releases/latest)) |
| iPhone / iPad | App Store → **RustDesk Remote Desktop** |
| Windows / Mac / Linux | [GitHub releases](https://github.com/rustdesk/rustdesk/releases/latest) |

## 2. Each PC you want to reach (unattended access)

Unattended access means you can connect any time, even when nobody is at the
PC. Both scripts download the latest official release, install it as a
service that starts at boot, set a permanent password, and print the **ID**.

**Windows** (right-click PowerShell → *Run as administrator*):

```powershell
cd path\to\remote-access
Set-ExecutionPolicy -Scope Process Bypass -Force
.\install-rustdesk-windows.ps1 -Password 'Choose-A-Strong-One'
```

**Ubuntu / Debian / Raspberry Pi OS 64-bit:**

```bash
chmod +x install-rustdesk-linux.sh
sudo ./install-rustdesk-linux.sh 'Choose-A-Strong-One'
```

Write down the printed ID. On your phone, open RustDesk, type the ID, tap
**Connect**, and enter the password.

Doing it by hand instead: install the app, then open **Settings → Security →
Unlock security settings → Use permanent password**, and keep
**Settings → General → Start on boot** turned on.

## 3. Optional: your own server

By default, RustDesk uses its free public servers to connect your devices.
These can be slow at peak times. For faster connections and full control,
run your own server with [`self-host/docker-compose.yml`](self-host/docker-compose.yml)
on any always-on Linux box. It can be a small VPS or an office machine with a
port forward. Then pass the server address and the contents of
`data/id_ed25519.pub` to the scripts:

```powershell
.\install-rustdesk-windows.ps1 -Password '...' -IdServer 'your.server' -Key 'PUBLIC_KEY'
```
```bash
sudo ./install-rustdesk-linux.sh '...' your.server 'PUBLIC_KEY'
```

Set the same server and key in your phone app under **Settings → ID/Relay
server**.

## Security notes

- Use a long, unique password for each PC. Anyone with the ID and password
  gets full control.
- Keep RustDesk updated. Re-running the script on a PC with RustDesk already
  installed only changes its configuration, so to update, uninstall first or
  use the app's built-in update prompt.
- Linux needs an X11 desktop session. On Wayland, choose "Xorg" at the login
  screen. For a headless Raspberry Pi edge gateway, use SSH instead.
- Don't install it on the FOD relay controller or any PLC/safety device. Install
  it only on the supervising PC.
