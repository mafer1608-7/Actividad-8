# Actividad 8 — Zonas virtualizadas de simulación físico-robótica controladas por ESP32 con plano de administración de red

**Autores:** María Fernanda Peñuela Romero · Alix Estefania Maldonado Roa · Juan David Artunduaga Diaz
**Curso:** Micros y laboratorio · **Fecha:** 7 de octubre de 2026
**Repositorio:** https://github.com/mafer1608-7/Actividad-8 · **Docker Hub:** https://hub.docker.com/u/mafepr08

Este repositorio contiene el desarrollo de la Actividad 8: un laboratorio con **ESP32, PyBullet, Docker, VLANs y MQTT** compuesto por tres redes aisladas y un router inter-VLAN.

| Red | Tema | Hardware principal | Software |
|---|---|---|---|
| **VLAN 1** | Zona Gamer Multijugador (carreras) | 3 × ESP32 maestras, potenciómetros | PyBullet + WebSocket (Docker) |
| **VLAN 2** | Zona de Simulación Robótica (Spot, Pepper, NAO) | 3 × ESP32 maestras, potenciómetros | PyBullet real-to-sim (Docker) |
| **VLAN 3** | Plano de administración de red | 1 × ESP32 esclava, 7 LEDs | Alpine + Mosquitto + monitor (Docker) |
| **Router** | Enrutamiento inter-VLAN con aislamiento | — | Alpine + iptables (Docker) |

---

## Contenido

- [Descripción general](#descripción-general)
- [Objetivos](#objetivos)
- [Arquitectura del sistema](#arquitectura-del-sistema)
- [VLAN 1 — Zona Gamer Multijugador](#vlan-1--zona-gamer-multijugador)
- [VLAN 2 — Zona de Simulación Robótica](#vlan-2--zona-de-simulación-robótica)
- [VLAN 3 — Plano de administración](#vlan-3--plano-de-administración)
- [Router inter-VLAN](#router-inter-vlan)
- [Hardware utilizado](#hardware-utilizado)
- [Software utilizado](#software-utilizado)
- [Funcionamiento del sistema](#funcionamiento-del-sistema)
- [Ejecución](#ejecución)
- [Validación experimental](#validación-experimental)
- [Imágenes en Docker Hub](#imágenes-en-docker-hub)
- [Organización del repositorio](#organización-del-repositorio)
- [Requisitos generales](#requisitos-generales)
- [Solución de problemas](#solución-de-problemas)
- [Evidencias](#evidencias)
- [Conclusiones](#conclusiones)

---

# Descripción general

En el desarrollo de sistemas embebidos modernos, los microcontroladores ya no operan de forma aislada: se integran con infraestructura virtualizada, redes segmentadas y simuladores físicos que replican el comportamiento de sistemas reales.

En esta actividad se construyó un laboratorio con dos zonas de simulación aisladas entre sí (una de carreras multijugador y una de robótica), un plano de administración que mide el desempeño de la red y un mecanismo de señalización física mediante LEDs que refleja en tiempo real el estado de cada contenedor. Se sigue un patrón **maestro–esclavo** entre los dispositivos embebidos:

- Las **ESP32 maestras** leen potenciómetros y controlan en tiempo real cada simulación (los robots siguen el movimiento físico, paradigma *real-to-sim*).
- La **ESP32 esclava** recibe el estado de los contenedores por MQTT y lo muestra con LEDs.

El proyecto integra:

- Contenedores Docker con redes segmentadas (VLANs).
- Simulación física con PyBullet (pista de carros y tres robots).
- Programación de ESP32 con Arduino/PlatformIO.
- Comunicación UDP entre ESP32 y contenedores, WebSocket entre contenedores y MQTT para telemetría.
- Medición de latencia, jitter y disponibilidad en un plano de administración independiente.
- Router inter-VLAN con reglas `iptables`.

# Objetivos

**Objetivo general.** Diseñar e implementar una arquitectura distribuida basada en contenedores Docker, segmentada en VLANs, donde múltiples microcontroladores ESP32 actúan como dispositivos de control en tiempo real sobre simulaciones físicas desarrolladas en PyBullet, y donde un plano de administración independiente mide el jitter, la latencia y el estado de cada zona, reflejando la actividad de los contenedores mediante indicadores LED controlados por una ESP32 esclava.

| # | Objetivo específico | Dónde se cumple |
|---|---|---|
| 1 | VLAN 1 (Gamer): servidor de pista PyBullet y tres clientes, cada uno controlado por una ESP32 maestra | `services/track_server`, `services/player`, `firmware/src/ctrl` |
| 2 | VLAN 2 (Robótica): Spot, Pepper y NAO en PyBullet, cada uno con su ESP32 maestra (*real-to-sim*) | `services/robot_sim`, `firmware/src/ctrl` |
| 3 | VLAN 3 (Administración): contenedor Alpine de monitoreo, broker MQTT y ESP32 esclava con LEDs | `services/admin`, `firmware/src/led_monitor` |
| 4 | Router inter-VLAN que permita al plano de administración observar ambas zonas sin romper su aislamiento | `services/router`, `tests/test_isolation.sh` |
| 5 | Validar experimentalmente la red mediante métricas de jitter, latencia y disponibilidad | `tools/`, sección [Validación experimental](#validación-experimental) |

---

# Arquitectura del sistema

```text
  ┌───────────────────────── VLAN 1 · Gamer 192.168.10.0/24 ─────────────────────────┐
  │  ESP32 ctrl-1/2/3 ──UDP──► player-1/2/3 ──WebSocket──► track-server (PyBullet)   │
  └───────────────────────────────────────┬──────────────────────────────────────────┘
                                          │
                                   ┌──────┴──────┐
                                   │   ROUTER    │   ip_forward + iptables
                                   │ .254 / VLAN │   VLAN1 ✗ VLAN2 (aislados)
                                   └──────┬──────┘
                                          │
  ┌───────────────────────── VLAN 2 · Robótica 192.168.20.0/24 ──────────────────────┐
  │  ESP32 ctrl-nao/spot/pepper ──UDP──► sim-nao · sim-spot · sim-pepper (PyBullet)  │
  └───────────────────────────────────────┬──────────────────────────────────────────┘
                          MQTT metrics + heartbeat UDP (solo estos puertos)
                                          │
  ┌───────────────────────── VLAN 3 · Administración 192.168.30.0/24 ───────────────┐
  │  admin (Alpine + Mosquitto + monitor)  ──MQTT lab/status/#──► ESP32 esclava      │
  │  mide latencia · jitter · disponibilidad                       7 LEDs            │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

La arquitectura es la sugerida en el enunciado, con dos decisiones propias: se usan **7 LEDs** (uno por contenedor monitoreado: track-server, 3 players y 3 robots) y el broker MQTT corre dentro del contenedor `admin`.

## Direccionamiento

| Red | Subred | Contenedores | Puertos publicados en el host |
|---|---|---|---|
| VLAN 1 Gamer | 192.168.10.0/24 | track-server `.10`, player-1 `.11`, player-2 `.12`, player-3 `.13`, router `.254` | UDP 5001 / 5002 / 5003 |
| VLAN 2 Robótica | 192.168.20.0/24 | sim-nao `.11`, sim-spot `.12`, sim-pepper `.13`, router `.254` | UDP 5011 / 5012 / 5013 |
| VLAN 3 Admin | 192.168.30.0/24 | admin `.10`, router `.254` | TCP 1883 (MQTT), UDP 9999 (heartbeat), TCP 8080 (dashboard) |

Cada VLAN se implementa como una **red bridge de Docker** independiente, con su propia subred y dominio de broadcast. Existe además la variante con VLAN 802.1Q reales usando redes `macvlan` (`parent: eth0.10`, `eth0.20`, `eth0.30`), que no es la configuración por defecto.

---

# VLAN 1 — Zona Gamer Multijugador

## Descripción

Zona de carreras multijugador. Un servidor de pista PyBullet recibe las órdenes de tres clientes; cada cliente es controlado por una ESP32 maestra.

## Componentes

| Contenedor | IP | Función |
|---|---|---|
| `track-server` | 192.168.10.10 | PyBullet headless con pista elíptica y 3 coches (`racecar.urdf`). API WebSocket |
| `player-1/2/3` | 192.168.10.11-13 | Reciben UDP de su ESP32 y lo reenvían al servidor. Color y estilo configurables |

## Funcionamiento

1. La ESP32 maestra envía por UDP `CMD,<id>,<seq>,<ms>,<v1>,<v2>,<v3>` a 50 Hz.
2. El `player` convierte `v1` en dirección (el centro es recto) y `v2` en acelerador.
3. El `player` reenvía por WebSocket `{player, steer, throttle, color, style, gain}` al `track-server`.
4. Si un jugador deja de enviar durante más de 1 s, su coche pasa a **piloto automático** (seguimiento de waypoints de la pista).

Estilos de conducción (`CAR_STYLE`): `sport` (ganancia 1.0), `classic` (0.7) y `drift` (1.2). El color se define con `CAR_COLOR` (RGB entre 0 y 1).

# VLAN 2 — Zona de Simulación Robótica

## Descripción

Tres contenedores independientes (Spot, Pepper y NAO) en PyBullet, cada uno controlado por su propia ESP32 maestra bajo el paradigma *real-to-sim*.

## Componentes

| Contenedor | IP | Robot | Modelo por defecto |
|---|---|---|---|
| `sim-spot` | 192.168.20.12 | Cuadrúpedo | `a1/a1.urdf` (pybullet_data) |
| `sim-nao` | 192.168.20.11 | Humanoide pequeño | `humanoid/humanoid.urdf` escalado |
| `sim-pepper` | 192.168.20.13 | Humanoide grande | `humanoid/humanoid.urdf` escalado |

## Funcionamiento

Los tres valores analógicos de la ESP32 (0–4095) se asignan a **tres grupos de articulaciones** del robot; cada valor define la posición objetivo entre los límites de sus articulaciones. Al girar un potenciómetro real, el robot simulado se mueve de forma equivalente.

Para usar los modelos de los repositorios de referencia, se clonan en `./models/`, se descomenta el volumen `./models:/models:ro` en `docker-compose.yml` y se define `URDF=/models/<ruta>/robot.urdf` (opcionalmente `BASE_Z` y `SCALE`).

| Repositorio de referencia | Uso en el proyecto |
|---|---|
| [rl-baselines3-zoo](https://github.com/DLR-RM/rl-baselines3-zoo) | Referencia para la pista de carros con PyBullet |
| [rex-gym](https://github.com/nicrusso7/rex-gym) | Referencia del cuadrúpedo (Spot) |
| [humanoid-gym](https://github.com/0aqz0/humanoid-gym) | Referencia de los humanoides (NAO/Pepper) |

# VLAN 3 — Plano de administración

## Descripción

Plano independiente que observa ambas zonas, mide el desempeño de la red y señaliza el estado de cada contenedor.

## Componentes

| Elemento | Función |
|---|---|
| `admin` (192.168.30.10) | Alpine con Mosquitto y `monitor.py`. Calcula latencia, jitter, pérdida y disponibilidad. Publica el estado y expone un dashboard en `:8080` |
| ESP32 esclava `led-monitor` | Suscrita a `lab/status/#`, enciende un LED por contenedor |

## Métricas y estados

| Métrica | Cómo se mide |
|---|---|
| Latencia | RTT de `ping` a cada contenedor (1 Hz) |
| Jitter | Variación entre el tiempo de llegada y el de emisión de los paquetes (estimador RFC 3550, `common/jitter.py`) |
| Pérdida | Huecos en el número de secuencia |
| Disponibilidad | % de pings respondidos en una ventana de 300 s |

| Estado | Condición | LED |
|---|---|---|
| `UP` | Ping y métricas correctos | Encendido fijo |
| `DEGRADED` | Latencia > 50 ms, jitter > 30 ms o sin métricas recientes | Parpadeo lento |
| `DOWN` | Sin ping y sin métricas | Apagado |
| Sin MQTT | La esclava no alcanza el broker | Todos parpadean rápido |

Los umbrales se configuran con `RTT_WARN_MS`, `JITTER_WARN_MS` y `STALE_S` en `docker-compose.yml`.

# Router inter-VLAN

Contenedor Alpine conectado a las tres redes (`.254` en cada una) con `ip_forward=1` y política `FORWARD DROP`. Cada contenedor instala rutas estáticas hacia las otras subredes mediante `STATIC_ROUTES` (`common/entrypoint.sh`).

| Origen → Destino | Política |
|---|---|
| VLAN 1 ↔ VLAN 2 | **Bloqueado** (aislamiento total) |
| VLAN 3 → VLAN 1 / VLAN 2 | Solo ICMP echo (latencia y disponibilidad) |
| VLAN 1 / VLAN 2 → admin | Solo MQTT 1883/tcp y heartbeat 9999/udp |
| Cualquier otro tráfico | Bloqueado |

---

# Hardware utilizado

- 6 × ESP32 DevKit como maestras (3 en VLAN 1 y 3 en VLAN 2) y 1 × ESP32 DevKit como esclava.
- 3 potenciómetros de 10 kΩ por ESP32 maestra.
- 7 × LED y 7 × resistencias de 220 Ω.
- Protoboard, cables Dupont y cables USB de datos.
- Computador con Docker y red WiFi de 2.4 GHz.

## Conexiones de las ESP32 maestras

| Elemento | ESP32 | Función |
|---|---|---|
| Potenciómetro A | GPIO 34 | `v1` (dirección o grupo 1 de articulaciones) |
| Potenciómetro B | GPIO 35 | `v2` (acelerador o grupo 2) |
| Potenciómetro C | GPIO 32 | `v3` (grupo 3) |
| LED integrado | GPIO 2 | Indicador de WiFi conectado |

Cada potenciómetro se conecta con un extremo a 3V3, el otro a GND y el cursor al GPIO.

## Conexiones de la ESP32 esclava (LEDs)

Cada GPIO se conecta a una resistencia de 220 Ω, luego al LED y finalmente a GND.

| LED | GPIO | Contenedor |
|---|---|---|
| 1 | 13 | track-server |
| 2 | 14 | player-1 |
| 3 | 16 | player-2 |
| 4 | 17 | player-3 |
| 5 | 18 | sim-nao |
| 6 | 19 | sim-spot |
| 7 | 21 | sim-pepper |

---

# Software utilizado

## ESP32 (Arduino / PlatformIO)

```text
firmware/
├── platformio.ini
├── include/secrets.h.example
└── src/
    ├── ctrl/main.cpp          # ESP32 maestra
    └── led_monitor/main.cpp   # ESP32 esclava
```

- **ctrl/main.cpp**: lee los tres potenciómetros y envía `CMD` a 50 Hz al contenedor y `HB` (heartbeat) a 10 Hz al administrador.
- **led_monitor/main.cpp**: se suscribe a `lab/status/#` y controla los 7 LEDs.
- `platformio.ini` define un entorno por dispositivo: `ctrl-1`, `ctrl-2`, `ctrl-3`, `ctrl-nao`, `ctrl-spot`, `ctrl-pepper` y `led-monitor`.

## Contenedores

| Imagen | Base | Contenido |
|---|---|---|
| `lab-sim-base` | python:3.10-slim | PyBullet, NumPy, paho-mqtt, websockets |
| `lab-router` | alpine:3.20 | iptables, iproute2, tc |
| `lab-admin` | alpine:3.20 | Mosquitto, Python 3, monitor |
| `lab-track-server` | lab-sim-base | Servidor de pista |
| `lab-player` | lab-sim-base | Cliente de pista |
| `lab-robot-sim` | lab-sim-base | Simulador de robots |

## Protocolos y tópicos

| Canal | Formato |
|---|---|
| ESP32 → contenedor | UDP `CMD,id,seq,ms,v1,v2,v3` |
| ESP32 → admin | UDP `HB,id,seq,ms` |
| player → track-server | WebSocket JSON `{player, steer, throttle, color, style, gain}` |
| contenedor → admin | MQTT `metrics/<nombre>` (JSON) |
| admin → LEDs | MQTT `lab/status/<nombre>` = `UP` / `DEGRADED` / `DOWN` (retenido) |
| admin → dashboard | MQTT `lab/metrics/<nombre>` (JSON) y HTTP `:8080` |

---

# Funcionamiento del sistema

### 1. Lectura de los potenciómetros

Cada ESP32 maestra lee tres entradas analógicas (12 bits, promedio de 4 lecturas) y arma el paquete UDP con un número de secuencia y su marca de tiempo (`millis`).

### 2. Envío al contenedor

El paquete `CMD` se envía a la IP del computador y al puerto publicado del contenedor correspondiente.

### 3. Simulación

- **VLAN 1:** el `player` reenvía la orden al `track-server`, que mueve el coche en PyBullet.
- **VLAN 2:** el simulador mapea los valores a las articulaciones del robot.

### 4. Telemetría

Cada contenedor publica cada segundo en `metrics/<nombre>` su tasa de paquetes, pérdidas, jitter y frecuencia de simulación. El tráfico atraviesa el router, que solo permite MQTT hacia el administrador.

### 5. Medición y clasificación

`monitor.py` combina el ping, el heartbeat de las ESP32 y la telemetría, clasifica cada contenedor en `UP`, `DEGRADED` o `DOWN`, y guarda cada muestra en `data/metrics.csv`.

### 6. Señalización

La ESP32 esclava recibe `lab/status/<nombre>` y enciende, hace parpadear o apaga el LED correspondiente.

## Secuencia de operación

1. El usuario mueve un potenciómetro de una ESP32 maestra.
2. La ESP32 envía el paquete UDP al contenedor de su zona.
3. El contenedor actualiza la simulación PyBullet.
4. El contenedor publica sus métricas por MQTT hacia la VLAN 3.
5. El administrador mide latencia, jitter y disponibilidad.
6. El administrador publica el estado de cada contenedor.
7. La ESP32 esclava refleja el estado en los LEDs.

## Comunicaciones utilizadas

| Comunicación | Función |
|---|---|
| ADC / GPIO | Lectura de potenciómetros y control de LEDs |
| WiFi + UDP | ESP32 maestra → contenedor y heartbeat |
| WebSocket | player → track-server |
| MQTT | Telemetría y estado de los contenedores |
| ICMP | Medición de latencia y disponibilidad |
| Docker networks + iptables | Segmentación en VLANs y aislamiento |

---

# Ejecución

## 1. Configurar y levantar los contenedores

Desde la carpeta del proyecto, con Docker y `make` instalados:

```bash
cp .env.example .env          # ya incluye DOCKERHUB_USER=mafepr08
make up                       # construye la base (compila PyBullet, ~5 min la primera vez) y levanta todo
make test                     # valida el aislamiento entre VLAN
```

Dashboard del plano de administración: http://localhost:8080

> Si las subredes `192.168.10/20/30.0/24` ya las usa tu red local, Docker mostrará `Pool overlaps with other one`. Hay que cambiarlas en `docker-compose.yml`, `services/router/router.sh` y `services/admin/monitor.py`.

## 2a. Sin hardware (ESP32 virtuales)

El emulador envía el mismo protocolo UDP que el firmware real:

```bash
make emulate                                              # lanza 6 ESP32 virtuales
mosquitto_sub -h localhost -t 'lab/status/#' -v           # estado que verían los LEDs
```

## 2b. Con hardware

1. Copiar `firmware/include/secrets.h.example` a `firmware/include/secrets.h` y completar `WIFI_SSID`, `WIFI_PASS` y `HOST_IP` (IP LAN del computador con Docker).
2. Abrir en el firewall del computador los puertos UDP 5001-5003, 5011-5013, 9999 y TCP 1883.
3. Programar cada ESP32 maestra con su entorno:

```bash
cd firmware
pio run -e ctrl-1 -t upload
pio run -e ctrl-2 -t upload
pio run -e ctrl-3 -t upload
pio run -e ctrl-nao -t upload
pio run -e ctrl-spot -t upload
pio run -e ctrl-pepper -t upload
pio run -e led-monitor -t upload      # ESP32 esclava
```

> Cerrar cualquier monitor serie abierto antes de subir el firmware.

## 3. Apagar el laboratorio

```bash
make down
```

---

# Validación experimental

Todos los experimentos escriben en `data/metrics.csv` y se analizan con:

```bash
python3 tools/analyze_metrics.py data/metrics.csv --since <ts> --until <ts> --plot
```

(`date +%s` permite anotar los tiempos de inicio y fin de cada experimento.)

| Exp. | Procedimiento | Resultado esperado |
|---|---|---|
| E0 Aislamiento | `make test` | VLAN 1 ↔ VLAN 2 bloqueado; admin alcanza ambas; zonas → admin solo 1883 y 9999 |
| E1 Línea base | `make emulate` durante 5 min | Los 7 contenedores en `UP`, RTT bajo, disponibilidad cercana al 100 % |
| E2 Latencia | `tools/inject_latency.sh 20 100 20` (100 ms ± 20 en VLAN 2) | `sim-*` pasan a `DEGRADED`. `tools/inject_latency.sh 20 clear` restablece |
| E3 Jitter y pérdida | `python3 tools/esp32_emulator.py --id ctrl-1 --cmd-port 5001 --jitter-ms 80 --drop 0.1` | Suben el jitter y la pérdida; `player-1` pasa a `DEGRADED` |
| E4 Disponibilidad | `docker stop sim-spot`, esperar 30 s, `docker start sim-spot` | `sim-spot` pasa a `DOWN` y se recupera |
| E5 Aislamiento bajo carga | Repetir E0 durante E2 | El router sigue bloqueando VLAN 1 ↔ VLAN 2 |

## Resultados

> Las mediciones se realizan con las **ESP32 virtuales** (`make emulate`), porque no se dispuso de las placas físicas. El firmware de `firmware/` está escrito para el hardware real, pero no se probó físicamente.

| Experimento | Contenedor | RTT medio (ms) | RTT p95 (ms) | Jitter medio (ms) | Disponibilidad (%) | Estado |
|---|---|---|---|---|---|---|
| E1 | player-1 | | | | | |
| E2 | sim-nao | | | | | |
| E3 | player-1 | | | | | |
| E4 | sim-spot | | | | | |

---

# Imágenes en Docker Hub

```bash
docker login
make push
```

| Imagen | Enlace |
|---|---|
| lab-sim-base | https://hub.docker.com/r/mafepr08/lab-sim-base |
| lab-router | https://hub.docker.com/r/mafepr08/lab-router |
| lab-admin | https://hub.docker.com/r/mafepr08/lab-admin |
| lab-track-server | https://hub.docker.com/r/mafepr08/lab-track-server |
| lab-player | https://hub.docker.com/r/mafepr08/lab-player |
| lab-robot-sim | https://hub.docker.com/r/mafepr08/lab-robot-sim |

---

# Organización del repositorio

```text
Actividad-8/
│
├── docker-compose.yml        # 3 redes + 9 contenedores
├── Makefile                  # base | build | up | test | emulate | analyze | push
├── .env.example
├── README.md
│
├── common/
│   ├── jitter.py             # jitter RFC 3550, pérdida y tasa
│   ├── mqtt_util.py          # cliente y publicador de métricas
│   └── entrypoint.sh         # rutas estáticas inter-VLAN
│
├── docker/base/Dockerfile    # imagen base con PyBullet
│
├── services/
│   ├── router/               # Alpine + iptables
│   ├── admin/                # Alpine + Mosquitto + monitor.py
│   ├── track_server/         # pista PyBullet + WebSocket
│   ├── player/               # cliente UDP → WebSocket
│   └── robot_sim/            # PyBullet real-to-sim
│
├── firmware/
│   ├── platformio.ini
│   ├── include/secrets.h.example
│   └── src/
│       ├── ctrl/main.cpp
│       └── led_monitor/main.cpp
│
├── tools/
│   ├── esp32_emulator.py
│   ├── launch_emulators.py
│   ├── inject_latency.sh
│   └── analyze_metrics.py
│
├── tests/test_isolation.sh
├── scripts/push_images.sh
└── data/                     # metrics.csv generado por el administrador
```

---

# Requisitos generales

| Elemento | Requisito |
|---|---|
| Sistema | Linux, macOS o Windows con WSL2 |
| Contenedores | Docker y Docker Compose v2 |
| Herramientas | `make`, Python 3, PlatformIO (solo con hardware) |
| Red | Subredes 192.168.10/20/30.0/24 libres; WiFi 2.4 GHz (solo con hardware) |
| Placas | 7 × ESP32 DevKit (opcional, existe emulador) |
| Periféricos | 3 potenciómetros por maestra, 7 LEDs con resistencias de 220 Ω |
| Librerías (contenedores) | pybullet, numpy, paho-mqtt, websockets |
| Librerías (ESP32) | PubSubClient (solo la esclava) |

---

# Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `Pool overlaps with other one` | La red local usa las mismas subredes | Cambiar las subredes en `docker-compose.yml`, `router.sh` y `monitor.py` |
| Todos los contenedores en `DOWN` al inicio | El administrador necesita unos segundos para medir | Esperar unos 5 s |
| `DEGRADED` con `sin-metricas` | Fallan las rutas o el firewall del router | `docker exec router iptables -L FORWARD -nv` y revisar `STATIC_ROUTES` |
| La ESP32 no llega al contenedor | `HOST_IP` incorrecta o firewall del computador | Verificar IP y puertos; probar antes con `make emulate` |
| `iptables` falla en el router | El kernel del host no tiene `nf_conntrack` | Usar el paquete `iptables-legacy` en el router |
| El coche gira o avanza al revés | El signo depende del URDF | Ajustar el signo en `Track.apply_controls()` |
| `a1/a1.urdf` no se encuentra | La versión de `pybullet_data` no lo incluye | Usar `URDF=` con un modelo de los repositorios de referencia |
| Error de puerto ocupado al subir el firmware | Otro programa usa el puerto serie | Cerrar monitores serie y volver a subir |
| El LED no enciende | Cableado, polaridad o resistencia | Revisar GPIO, LED (pata larga al GPIO) y GND |

---

# Evidencias

## Resultados experimentales

Las tablas y gráficas generadas por `tools/analyze_metrics.py` se agregan en la carpeta `evidencias/` una vez ejecutados los experimentos.

## Video

No se incluye video del funcionamiento con hardware real, porque no se dispuso de las ESP32 físicas.

---

# Conclusiones

La actividad integra contenedores Docker, redes segmentadas, simulación física y microcontroladores en una sola arquitectura. La segmentación en tres redes con un router que solo permite el tráfico estrictamente necesario muestra cómo aislar zonas de simulación y, al mismo tiempo, mantener un plano de administración que las observa.

El patrón maestro–esclavo se aplica en dos niveles: las ESP32 maestras controlan en tiempo real cada simulación (los robots reproducen el movimiento de los potenciómetros), y la ESP32 esclava refleja con LEDs el estado calculado por el administrador a partir de la latencia, el jitter y la disponibilidad.

El emulador de ESP32 permite validar la arquitectura completa sin hardware, y el uso de un único protocolo entre el firmware y el emulador facilita pasar después a las placas reales. Como trabajo futuro quedan la validación del firmware en las ESP32 físicas, el uso de los modelos originales de los repositorios de referencia, la autenticación y el cifrado TLS en MQTT, y el enrutamiento dinámico con FRR.
