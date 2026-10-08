"""Estadísticas de un flujo UDP (seq, ms_del_emisor): jitter estilo RFC 3550, pérdidas y tasa."""
import time
from collections import deque


class StreamStats:
    def __init__(self):
        self.last_seq = None
        self.last_arr = None
        self.last_snd = None
        self.jitter = 0.0      # ms
        self.rx = 0
        self.lost = 0
        self.last_rx_time = 0.0
        self.win = deque()

    def update(self, seq, sender_ms):
        now = time.monotonic()
        arr = now * 1000.0
        if self.last_seq is not None:
            if seq > self.last_seq:
                self.lost += seq - self.last_seq - 1
            else:                      # el ESP32 se reinició o hubo reordenamiento
                self.last_arr = None
        if self.last_arr is not None:
            d = abs((arr - self.last_arr) - (sender_ms - self.last_snd))
            self.jitter += (d - self.jitter) / 16.0
        self.last_seq, self.last_arr, self.last_snd = seq, arr, sender_ms
        self.rx += 1
        self.last_rx_time = now
        self.win.append(now)

    def snapshot(self):
        now = time.monotonic()
        while self.win and self.win[0] < now - 2.0:
            self.win.popleft()
        return {
            "rx": self.rx,
            "lost": self.lost,
            "jitter_ms": round(self.jitter, 2),
            "rate_hz": round(len(self.win) / 2.0, 1),
            "age_s": round(now - self.last_rx_time, 2) if self.rx else None,
        }
