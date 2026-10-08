#!/usr/bin/env bash
# Valida el aislamiento entre VLAN y el acceso del plano de administración.
ok=0; fail=0
check() {  # descripción, esperado(0=éxito,1=bloqueado), comando...
  local desc="$1" expect="$2"; shift 2
  if "$@" >/dev/null 2>&1; then got=0; else got=1; fi
  if [ "$got" = "$expect" ]; then echo "  [OK]   $desc"; ok=$((ok+1)); else echo "  [FALLA] $desc"; fail=$((fail+1)); fi
}
P="ping -c1 -W1"
echo "== Aislamiento VLAN1 <-> VLAN2 (debe estar BLOQUEADO) =="
check "player-1 -> sim-nao (192.168.20.11)"  1 docker exec player-1 $P 192.168.20.11
check "sim-spot -> track-server (192.168.10.10)" 1 docker exec sim-spot $P 192.168.10.10
echo "== Plano de administración (debe ALCANZAR ambas zonas) =="
check "admin -> player-1 (VLAN1)" 0 docker exec admin ping -c1 -W1 192.168.10.11
check "admin -> sim-pepper (VLAN2)" 0 docker exec admin ping -c1 -W1 192.168.20.13
echo "== Zonas -> admin: solo MQTT (1883) permitido =="
check "player-1 -> admin:1883 (MQTT)" 0 docker exec player-1 nc -z -w2 192.168.30.10 1883
check "sim-nao -> admin:1883 (MQTT)"  0 docker exec sim-nao nc -z -w2 192.168.30.10 1883
check "player-1 -> admin:8080 (HTTP)  bloqueado" 1 docker exec player-1 nc -z -w2 192.168.30.10 8080
echo
echo "Resultado: $ok OK, $fail con fallo"
docker exec router iptables -L FORWARD -n -v | head -20
[ "$fail" = 0 ]
