#!/usr/bin/env bash
# wan-monitor.sh — health-check both Wi-Fi WAN uplinks and keep the default
# route balanced (both up), failed over (one up), or untouched (both down,
# gateway falls back to offline-first + SMS). Installed by
# wifi-loadbalancer.sh; runs as a systemd service. Status is written to
# /run/wan-monitor.status for the dashboard's connectivity chip.
#
# Usage: wan-monitor.sh <if-a> <if-b> <weight-a> <weight-b>
set -u

IF_A=${1:-wlan0}; IF_B=${2:-wlan1}
WEIGHT_A=${3:-1}; WEIGHT_B=${4:-1}
INTERVAL=10
STATUS_FILE=/run/wan-monitor.status
PING_TARGETS=(1.1.1.1 8.8.8.8)

gateway_of() { nmcli -g IP4.GATEWAY device show "$1" 2>/dev/null | head -n1; }

# Up = the interface has a gateway and at least one target answers a ping
# routed out of that specific interface.
link_up() {
  local ifc=$1 gw target
  gw=$(gateway_of "$ifc"); [[ -n $gw ]] || return 1
  for target in "${PING_TARGETS[@]}"; do
    ping -c1 -W2 -I "$ifc" "$target" >/dev/null 2>&1 && return 0
  done
  return 1
}

apply_routes() {
  local mode=$1
  case $mode in
    balanced)
      ip route replace default \
        nexthop via "$(gateway_of "$IF_A")" dev "$IF_A" weight "$WEIGHT_A" \
        nexthop via "$(gateway_of "$IF_B")" dev "$IF_B" weight "$WEIGHT_B" ;;
    only-a) ip route replace default via "$(gateway_of "$IF_A")" dev "$IF_A" ;;
    only-b) ip route replace default via "$(gateway_of "$IF_B")" dev "$IF_B" ;;
  esac
}

last_mode=""
while true; do
  up_a=down; up_b=down
  link_up "$IF_A" && up_a=up
  link_up "$IF_B" && up_b=up

  if   [[ $up_a == up && $up_b == up ]]; then mode=balanced
  elif [[ $up_a == up ]];                then mode=only-a
  elif [[ $up_b == up ]];                then mode=only-b
  else                                        mode=offline
  fi

  if [[ $mode != "$last_mode" ]]; then
    case $mode in
      balanced) echo "A up, B up -> load balancing ${WEIGHT_A}:${WEIGHT_B}";;
      only-a)   echo "B DOWN -> all traffic via $IF_A";;
      only-b)   echo "A DOWN -> failover to $IF_B";;
      offline)  echo "BOTH UPLINKS DOWN -> keeping last route; gateway runs offline, SMS fallback active";;
    esac
    [[ $mode != offline ]] && apply_routes "$mode"
    last_mode=$mode
  fi

  echo "A=$up_a B=$up_b mode=$mode" > "$STATUS_FILE"
  sleep "$INTERVAL"
done
