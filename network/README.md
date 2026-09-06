# Wi-Fi WAN load balancer for the farm edge gateway

Gives the Raspberry Pi gateway **two internet uplinks over Wi-Fi** and balances
traffic across them, with automatic failover when one dies. Built for the
Phase-1 hardware in `BOM.md`:

- **Uplink A** — built-in Wi-Fi (`wlan0`) → the dual-SIM 4G router's SSID
  (Tenda 4G03 Pro / TP-Link MR110 class, Jio + Airtel)
- **Uplink B** — a USB Wi-Fi adapter (`wlan1`, ~₹500, any RTL8188/MT7601 dongle)
  → a second SSID: farmhouse broadband, a phone hotspot, or a second 4G router

```
 LoRa nodes ──► Pi gateway ──► wlan0 ──► 4G router (SIM1/SIM2) ──► internet
 (unchanged)        │
                    └────────► wlan1 ──► second Wi-Fi uplink   ──► internet
```

The dual-SIM router already fails over **between its two SIMs**; this adds a
second, independent path so the farm stays online even if that router (or the
whole tower) goes down. SMS via SIM800L remains the last-resort fallback —
nothing here touches it.

## What's in this folder

| File | Purpose |
|---|---|
| `wifi-loadbalancer.sh` | One-time setup: connects both Wi-Fi uplinks, installs the monitor |
| `wan-monitor.sh` | Health-checks each uplink every 10 s, rebalances/fails over routes |
| `wan-monitor.service` | systemd unit that keeps the monitor running from boot |

## Requirements

- Raspberry Pi OS Bookworm (NetworkManager-based — the default since 2023)
- A second Wi-Fi interface (USB dongle shows up as `wlan1`)
- Both uplinks on **different subnets** (e.g. router A `192.168.1.x`, router B
  `192.168.43.x`). If both routers use the same subnet, change the LAN subnet
  on one of them first.

## Install (run on the Pi)

```bash
cd ~/Anil/network
chmod +x wifi-loadbalancer.sh wan-monitor.sh
sudo ./wifi-loadbalancer.sh \
  --ssid-a "FARM-4G"     --pass-a "password-a" \
  --ssid-b "FARM-BACKUP" --pass-b "password-b"
```

Optional flags: `--if-a wlan0 --if-b wlan1` (interface names),
`--weight-a 3 --weight-b 1` (traffic split, default 1:1 — use 3:1 when uplink B
is a metered phone hotspot).

## Check it's working

```bash
ip route show                 # default route: two nexthops with weights
systemctl status wan-monitor  # active (running)
journalctl -u wan-monitor -f  # live health-check log
```

Pull the power on router A: within ~20 s the log shows `A DOWN -> failover to B`
and the dashboard/Home Assistant stay reachable. Plug it back in: routes
rebalance automatically.

## How it works

- Linux ECMP (equal-cost multipath) default route:
  `ip route replace default nexthop via <gwA> dev wlan0 weight 1 nexthop via <gwB> dev wlan1 weight 1`
  Per-connection balancing — one TCP stream sticks to one uplink (so MQTT,
  Home Assistant, Frigate uploads each ride a single path), new connections
  spread across both.
- `wan-monitor.sh` pings `1.1.1.1` and `8.8.8.8` out of each interface every
  10 s. Both up → multipath route with your weights. One down → single default
  route via the survivor. Both down → leaves last route in place (LoRa,
  schedules and SMS keep running — the gateway is offline-first by design).
- Everything is logged to the systemd journal; the dashboard's 4G status chip
  can later read `/run/wan-monitor.status` (`A=up B=down mode=failover`).

## Notes for this farm

- Mount the USB dongle's antenna outside the IP65 gateway box — ABS attenuates.
- On a metered hotspot uplink, set `--weight-a 9 --weight-b 1` so Frigate's
  camera traffic prefers the unlimited SIM; failover still uses B fully.
- Home Assistant, Node-RED and the dashboard bind to the LAN side and are
  unaffected; this only changes the Pi's *outbound* internet path.
