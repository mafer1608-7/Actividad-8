#!/bin/sh
# Instala rutas estáticas hacia otras VLAN a través del router inter-VLAN.
# STATIC_ROUTES="192.168.30.0/24@192.168.10.254 otra/red@gw"
for r in $STATIC_ROUTES; do
  net="${r%@*}"; gw="${r#*@}"
  ip route replace "$net" via "$gw" || echo "[entrypoint] no se pudo añadir ruta $net via $gw"
done
exec "$@"
