#!/usr/bin/env bash
# wifi-loadbalancer.sh — one-time setup of dual Wi-Fi WAN load balancing
# on the farm's Raspberry Pi edge gateway (Raspberry Pi OS Bookworm,
# NetworkManager). See network/README.md for the full guide.
#
# Usage:
#   sudo ./wifi-loadbalancer.sh --ssid-a "FARM-4G" --pass-a "secretA" \
#                               --ssid-b "FARM-BACKUP" --pass-b "secretB" \
#                               [--if-a wlan0] [--if-b wlan1] \
#                               [--weight-a 1] [--weight-b 1]
set -euo pipefail

IF_A=wlan0; IF_B=wlan1
SSID_A=""; PASS_A=""; SSID_B=""; PASS_B=""
WEIGHT_A=1; WEIGHT_B=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ssid-a)   SSID_A=$2; shift 2;;
    --pass-a)   PASS_A=$2; shift 2;;
    --ssid-b)   SSID_B=$2; shift 2;;
    --pass-b)   PASS_B=$2; shift 2;;
    --if-a)     IF_A=$2;   shift 2;;
    --if-b)     IF_B=$2;   shift 2;;
    --weight-a) WEIGHT_A=$2; shift 2;;
    --weight-b) WEIGHT_B=$2; shift 2;;
    *) echo "Unknown option: $1" >&2; exit 1;;
  esac
done

[[ $EUID -eq 0 ]] || { echo "Run with sudo."; exit 1; }
[[ -n $SSID_A && -n $SSID_B ]] || { echo "--ssid-a and --ssid-b are required."; exit 1; }
command -v nmcli >/dev/null || { echo "NetworkManager (nmcli) not found — needs Raspberry Pi OS Bookworm."; exit 1; }

for ifc in "$IF_A" "$IF_B"; do
  ip link show "$ifc" >/dev/null 2>&1 || {
    echo "Interface $ifc not found. Plug in the USB Wi-Fi adapter (shows up as wlan1)."; exit 1; }
done

echo "==> Connecting uplink A: $SSID_A on $IF_A"
nmcli connection delete wan-a >/dev/null 2>&1 || true
nmcli connection add type wifi con-name wan-a ifname "$IF_A" ssid "$SSID_A" \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASS_A" \
  ipv4.route-metric 100 ipv6.method disabled connection.autoconnect yes
nmcli connection up wan-a

echo "==> Connecting uplink B: $SSID_B on $IF_B"
nmcli connection delete wan-b >/dev/null 2>&1 || true
nmcli connection add type wifi con-name wan-b ifname "$IF_B" ssid "$SSID_B" \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASS_B" \
  ipv4.route-metric 200 ipv6.method disabled connection.autoconnect yes
nmcli connection up wan-b

GW_A=$(nmcli -g IP4.GATEWAY device show "$IF_A")
GW_B=$(nmcli -g IP4.GATEWAY device show "$IF_B")
[[ -n $GW_A && -n $GW_B ]] || { echo "Could not read gateways (A='$GW_A' B='$GW_B'). Are both SSIDs up?"; exit 1; }
if [[ ${GW_A%.*} == "${GW_B%.*}" ]]; then
  echo "WARNING: both uplinks look like the same subnet ($GW_A / $GW_B)."
  echo "Change the LAN subnet on one router or balancing will not work."
fi

echo "==> Installing wan-monitor (weights A=$WEIGHT_A B=$WEIGHT_B)"
SRC_DIR=$(cd "$(dirname "$0")" && pwd)
install -m 0755 "$SRC_DIR/wan-monitor.sh" /usr/local/sbin/wan-monitor.sh
sed -e "s|@IF_A@|$IF_A|" -e "s|@IF_B@|$IF_B|" \
    -e "s|@WEIGHT_A@|$WEIGHT_A|" -e "s|@WEIGHT_B@|$WEIGHT_B|" \
    "$SRC_DIR/wan-monitor.service" > /etc/systemd/system/wan-monitor.service
systemctl daemon-reload
systemctl enable --now wan-monitor.service

echo
echo "Done. Verify with:"
echo "  ip route show            # default route with two nexthops"
echo "  journalctl -u wan-monitor -f"
