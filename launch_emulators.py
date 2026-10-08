#!/usr/bin/env python3
"""Lanza las 6 ESP32 maestras virtuales a la vez. Ctrl+C para detenerlas."""
import subprocess
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
CTRL = {"ctrl-1": 5001, "ctrl-2": 5002, "ctrl-3": 5003, "ctrl-nao": 5011, "ctrl-spot": 5012, "ctrl-pepper": 5013}
procs = [subprocess.Popen([sys.executable, "tools/esp32_emulator.py", "--host", HOST, "--id", k, "--cmd-port", str(v)])
         for k, v in CTRL.items()]
try:
    for p in procs:
        p.wait()
except KeyboardInterrupt:
    for p in procs:
        p.terminate()
