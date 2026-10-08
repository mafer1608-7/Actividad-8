#!/usr/bin/env bash
# Inyecta latencia/jitter en el router hacia una VLAN (tc netem). Uso:
#   tools/inject_latency.sh <vlan: 10|20|30> <delay_ms> [jitter_ms]   |   tools/inject_latency.sh <vlan> clear
set -euo pipefail
VLAN="$1"; D="${2:-0}"; J="${3:-0}"
DEV=$(docker exec router sh -c "ip -o -4 addr show | grep '192.168.${VLAN}.254' | awk '{print \$2}'")
if [ "$D" = "clear" ]; then
  docker exec router tc qdisc del dev "$DEV" root || true; echo "netem eliminado en $DEV"
else
  docker exec router tc qdisc replace dev "$DEV" root netem delay "${D}ms" "${J}ms"
  echo "netem en $DEV (VLAN 192.168.${VLAN}.0/24): delay=${D}ms jitter=${J}ms"
fi
