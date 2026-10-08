#!/usr/bin/env python3
"""Resume data/metrics.csv: disponibilidad, latencia (media/p95/máx) y jitter por contenedor.
Opcional: --plot genera gráficas PNG (requiere matplotlib)."""
import argparse
import csv
import statistics as st
from collections import defaultdict

ap = argparse.ArgumentParser()
ap.add_argument("csv", nargs="?", default="data/metrics.csv")
ap.add_argument("--since", type=float, default=0, help="timestamp UNIX inicial (para aislar un experimento)")
ap.add_argument("--until", type=float, default=1e18)
ap.add_argument("--plot", action="store_true")
a = ap.parse_args()


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


rows = defaultdict(list)
with open(a.csv) as fh:
    for r in csv.DictReader(fh):
        ts = f(r["ts"])
        if ts and a.since <= ts <= a.until:
            rows[r["name"]].append(r)


def p95(v):
    v = sorted(v)
    return v[int(0.95 * (len(v) - 1))] if v else float("nan")


print(f"{'contenedor':14}{'n':>6}{'UP%':>7}{'DEGR%':>7}{'DOWN%':>7}{'rtt_med':>9}{'rtt_p95':>9}{'rtt_max':>9}{'jit_med':>9}{'jit_max':>9}")
for name, rs in sorted(rows.items()):
    n = len(rs)
    pct = lambda s: 100.0 * sum(1 for r in rs if r["state"] == s) / n
    rtt = [x for x in (f(r["rtt_ms"]) for r in rs) if x is not None]
    jit = []
    for r in rs:
        c = [x for x in (f(r["jitter_rx_ms"]), f(r["jitter_hb_ms"])) if x is not None]
        if c:
            jit.append(max(c))
    print(f"{name:14}{n:>6}{pct('UP'):>7.1f}{pct('DEGRADED'):>7.1f}{pct('DOWN'):>7.1f}"
          f"{(st.mean(rtt) if rtt else float('nan')):>9.2f}{p95(rtt):>9.2f}{(max(rtt) if rtt else float('nan')):>9.2f}"
          f"{(st.mean(jit) if jit else float('nan')):>9.2f}{(max(jit) if jit else float('nan')):>9.2f}")

if a.plot:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    for key, title in (("rtt_ms", "Latencia (ms)"), ("jitter_hb_ms", "Jitter heartbeat (ms)")):
        plt.figure(figsize=(10, 4))
        for name, rs in sorted(rows.items()):
            xs = [(f(r["ts"]) - f(rs[0]["ts"])) for r in rs if f(r[key]) is not None]
            ys = [f(r[key]) for r in rs if f(r[key]) is not None]
            if ys:
                plt.plot(xs, ys, label=name)
        plt.xlabel("tiempo (s)"); plt.ylabel(title); plt.legend(fontsize=7); plt.grid(alpha=.3)
        out = f"data/{key}.png"
        plt.savefig(out, dpi=120, bbox_inches="tight")
        print("guardado", out)
