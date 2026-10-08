#!/usr/bin/env python3
"""ESP32 maestra virtual: envía el mismo protocolo UDP que el firmware (CMD @50Hz y HB @10Hz).
Sirve para probar todo el laboratorio SIN hardware."""
import argparse
import math
import random
import socket
import time

ap = argparse.ArgumentParser()
ap.add_argument("--host", default="127.0.0.1", help="IP del PC que ejecuta Docker")
ap.add_argument("--id", default="ctrl-1")
ap.add_argument("--cmd-port", type=int, required=True)
ap.add_argument("--hb-port", type=int, default=9999)
ap.add_argument("--rate", type=float, default=50.0)
ap.add_argument("--jitter-ms", type=float, default=0.0, help="retardo aleatorio añadido antes de enviar")
ap.add_argument("--drop", type=float, default=0.0, help="probabilidad de descartar un paquete CMD")
a = ap.parse_args()

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
t0 = time.time()
seq = hbseq = 0
n_cmd = n_hb = time.monotonic()
print(f"[{a.id}] -> {a.host}:{a.cmd_port} (CMD) y :{a.hb_port} (HB)")
while True:
    now = time.monotonic()
    ms = int((time.time() - t0) * 1000)
    if now >= n_cmd:
        t = ms / 1000.0
        v = [int(2048 + 1800 * math.sin(t * w + ph)) for w, ph in ((0.8, 0), (0.5, 1.5), (0.3, 3))]
        v[1] = int(2048 + 2000 * math.sin(t * 0.5))          # throttle 0..4095
        pkt = f"CMD,{a.id},{seq},{ms},{v[0]},{v[1]},{v[2]}".encode()
        seq += 1
        n_cmd += 1.0 / a.rate
        if a.jitter_ms:
            time.sleep(random.uniform(0, a.jitter_ms) / 1000.0)
        if random.random() >= a.drop:
            s.sendto(pkt, (a.host, a.cmd_port))
    if now >= n_hb:
        s.sendto(f"HB,{a.id},{hbseq},{ms}".encode(), (a.host, a.hb_port))
        hbseq += 1
        n_hb += 0.1
    time.sleep(0.0005)
