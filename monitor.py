"""Plano de administración: mide latencia (ping), jitter (heartbeat/UDP), disponibilidad,
publica el estado de cada contenedor en MQTT (lab/status/<nombre>) y expone un dashboard HTTP."""
import csv
import json
import os
import re
import socket
import subprocess
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from common.jitter import StreamStats
from common.mqtt_util import make_client

# nombre del contenedor -> (IP, ESP32 maestra asociada)
TARGETS = {
    "track-server": ("192.168.10.10", None),
    "player-1": ("192.168.10.11", "ctrl-1"),
    "player-2": ("192.168.10.12", "ctrl-2"),
    "player-3": ("192.168.10.13", "ctrl-3"),
    "sim-nao": ("192.168.20.11", "ctrl-nao"),
    "sim-spot": ("192.168.20.12", "ctrl-spot"),
    "sim-pepper": ("192.168.20.13", "ctrl-pepper"),
}
RTT_WARN = float(os.getenv("RTT_WARN_MS", "50"))
JITTER_WARN = float(os.getenv("JITTER_WARN_MS", "30"))
STALE_S = float(os.getenv("STALE_S", "3"))
HB_PORT, HTTP_PORT = 9999, 8080
CSV_PATH = os.getenv("CSV_PATH", "/data/metrics.csv")

lock = threading.Lock()
rtt = {n: None for n in TARGETS}
ping_hist = {n: deque(maxlen=300) for n in TARGETS}
metrics = {}      # nombre -> (dict, t_recepción)
hb = {}           # ctrl-id -> StreamStats
latest = {}       # último estado calculado (para el dashboard)
PING_RE = re.compile(r"time=([\d.]+)")


def ping(ip):
    try:
        out = subprocess.run(["ping", "-c", "1", "-W", "1", ip], capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return None
    m = PING_RE.search(out)
    return float(m.group(1)) if m else None


def ping_loop():
    names = list(TARGETS)
    with ThreadPoolExecutor(max_workers=len(names)) as ex:
        while True:
            t0 = time.monotonic()
            res = dict(zip(names, ex.map(lambda n: ping(TARGETS[n][0]), names)))
            with lock:
                for n, r in res.items():
                    rtt[n] = r
                    ping_hist[n].append(r is not None)
            time.sleep(max(0.0, 1.0 - (time.monotonic() - t0)))


def hb_listener():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", HB_PORT))
    while True:
        data, _ = s.recvfrom(256)
        try:
            p = data.decode(errors="ignore").strip().split(",")
            if p[0] != "HB":
                continue
            with lock:
                hb.setdefault(p[1], StreamStats()).update(int(p[2]), int(p[3]))
        except Exception:
            continue


def evaluate(name, now):
    ip, ctrl = TARGETS[name]
    r = rtt[name]
    m, mt = metrics.get(name, (None, 0))
    fresh = m is not None and now - mt < STALE_S
    hbs = hb[ctrl].snapshot() if ctrl in hb else None
    hb_ok = hbs is not None and hbs["age_s"] is not None and hbs["age_s"] < STALE_S
    jit_rx = m.get("jitter_ms") if fresh and (m.get("age_s") is not None and m["age_s"] < STALE_S) else None
    jit_hb = hbs["jitter_ms"] if hb_ok else None
    reasons = []
    if r is None and not fresh:
        state = "DOWN"
    else:
        if r is None:
            reasons.append("sin-ping")
        elif r > RTT_WARN:
            reasons.append("latencia-alta")
        if not fresh:
            reasons.append("sin-metricas")
        if any(j is not None and j > JITTER_WARN for j in (jit_rx, jit_hb)):
            reasons.append("jitter-alto")
        state = "DEGRADED" if reasons else "UP"
    h = ping_hist[name]
    return {
        "name": name, "ip": ip, "ctrl": ctrl, "state": state, "reasons": reasons,
        "rtt_ms": r, "jitter_rx_ms": jit_rx, "jitter_hb_ms": jit_hb,
        "loss_hb": hbs["lost"] if hb_ok else None,
        "rate_hz": m.get("rate_hz") if fresh else None,
        "sim_hz": m.get("sim_hz") if fresh else None,
        "availability_pct": round(100.0 * sum(h) / len(h), 1) if h else None,
        "ts": round(now, 3),
    }


CSV_FIELDS = ["ts", "name", "state", "rtt_ms", "jitter_rx_ms", "jitter_hb_ms", "loss_hb",
              "rate_hz", "sim_hz", "availability_pct"]


def publish_loop(client):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        while True:
            now = time.time()
            with lock:
                recs = [evaluate(n, now) for n in TARGETS]
            for r in recs:
                client.publish(f"lab/status/{r['name']}", r["state"], retain=True)
                client.publish(f"lab/metrics/{r['name']}", json.dumps(r))
                w.writerow(r)
            f.flush()
            latest.clear()
            latest.update({r["name"]: r for r in recs})
            time.sleep(1.0)


HTML = """<!doctype html><meta charset=utf-8><title>Admin VLAN3</title>
<style>body{font-family:sans-serif;margin:2rem}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:4px 10px}
.UP{background:#c8f7c5}.DEGRADED{background:#ffe9a8}.DOWN{background:#f7b5b5}</style>
<h2>Plano de administración - estado de contenedores</h2><table id=t></table>
<script>
async function r(){const s=await (await fetch('/api/state')).json();
let h='<tr><th>Contenedor<th>IP<th>Estado<th>RTT ms<th>Jitter rx<th>Jitter HB<th>Pérdida HB<th>Hz<th>Disp. %<th>Motivo</tr>';
for(const k in s){const x=s[k];h+=`<tr><td>${k}<td>${x.ip}<td class=${x.state}>${x.state}<td>${x.rtt_ms??'-'}<td>${x.jitter_rx_ms??'-'}<td>${x.jitter_hb_ms??'-'}<td>${x.loss_hb??'-'}<td>${x.sim_hz??'-'}<td>${x.availability_pct??'-'}<td>${x.reasons.join(', ')}</tr>`}
document.getElementById('t').innerHTML=h}
setInterval(r,1000);r();</script>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/state"):
            body, ctype = json.dumps(latest).encode(), "application/json"
        else:
            body, ctype = HTML.encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    client = make_client("admin-monitor")

    def on_connect(c, u, flags, rc, *a):
        c.subscribe("metrics/#")

    def on_message(c, u, msg):
        try:
            d = json.loads(msg.payload)
            name = d.get("name") or msg.topic.split("/", 1)[1]
            with lock:
                metrics[name] = (d, time.time())
        except Exception:
            pass

    client.on_connect, client.on_message = on_connect, on_message
    client.connect_async("127.0.0.1", 1883)
    client.loop_start()
    for fn in (ping_loop, hb_listener):
        threading.Thread(target=fn, daemon=True).start()
    threading.Thread(target=publish_loop, args=(client,), daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
