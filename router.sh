#!/bin/sh
# Router inter-VLAN: aísla VLAN1 <-> VLAN2 y deja que el plano de administración (VLAN3) observe ambas.
V1=192.168.10.0/24
V2=192.168.20.0/24
V3=192.168.30.0/24
ADMIN=192.168.30.10

sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
echo "ip_forward = $(cat /proc/sys/net/ipv4/ip_forward)"

iptables -F FORWARD
iptables -P FORWARD DROP
iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Admin -> zonas: SOLO ICMP echo (medición de latencia / disponibilidad)
iptables -A FORWARD -s $V3 -d $V1 -p icmp --icmp-type echo-request -j ACCEPT
iptables -A FORWARD -s $V3 -d $V2 -p icmp --icmp-type echo-request -j ACCEPT

# Zonas -> admin: SOLO MQTT (telemetría) y heartbeat UDP
for Z in $V1 $V2; do
  iptables -A FORWARD -s $Z -d $ADMIN -p tcp --dport 1883 -j ACCEPT
  iptables -A FORWARD -s $Z -d $ADMIN -p udp --dport 9999 -j ACCEPT
done

# VLAN1 <-> VLAN2: NO hay regla de ACCEPT -> política DROP (aislamiento total)
echo "== Reglas FORWARD =="
iptables -L FORWARD -n -v --line-numbers
exec tail -f /dev/null
