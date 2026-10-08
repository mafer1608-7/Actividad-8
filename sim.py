"""sim-<robot> (VLAN2): simulación PyBullet 'real-to-sim'. Los 3 valores analógicos de la ESP32
(0-4095) se mapean a 3 grupos de articulaciones del robot.

Modelos por defecto (vienen con pybullet_data para que funcione sin descargas):
  spot -> a1/a1.urdf   nao/pepper -> humanoid/humanoid.urdf (escalado)
Para usar los modelos de los repositorios del curso (rex-gym, humanoid-gym) monta el URDF en /models
y define URDF=/models/ruta/robot.urdf (ver README)."""
import os
import socket
import threading
import time

import pybullet as p
import pybullet_data

from common.jitter import StreamStats
from common.mqtt_util import MetricsPublisher

NAME = os.getenv("ROBOT_NAME", "spot")
PORT = int(os.getenv("UDP_PORT", "5000"))
HZ = 240
# nombre: (urdf, z_inicial, escala, color)
DEFAULTS = {
    "spot": ("a1/a1.urdf", 0.45, 1.0, [1.0, 0.85, 0.0, 1]),
    "nao": ("humanoid/humanoid.urdf", 0.42, 0.33, [0.2, 0.4, 1.0, 1]),
    "pepper": ("humanoid/humanoid.urdf", 0.85, 0.70, [1.0, 1.0, 1.0, 1]),
}
URDF, Z0, SCALE, COLOR = DEFAULTS[NAME]
URDF = os.getenv("URDF", URDF)
Z0 = float(os.getenv("BASE_Z", Z0))
SCALE = float(os.getenv("SCALE", SCALE))
FIX_BASE = os.getenv("FIX_BASE", "1") == "1"

stats = StreamStats()
lock = threading.Lock()
cmd = {"v": [2048, 2048, 2048], "t": 0.0, "bad": 0}


def rx_thread():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", PORT))
    while True:
        data, _ = s.recvfrom(512)
        try:
            q = data.decode().strip().split(",")          # CMD,id,seq,ms,v1,v2,v3
            if q[0] != "CMD":
                continue
            vals = [int(x) for x in q[4:7]]
            with lock:
                stats.update(int(q[2]), int(q[3]))
                cmd["v"], cmd["t"] = vals, time.monotonic()
        except Exception:
            cmd["bad"] += 1


def main():
    p.connect(p.GUI if os.getenv("GUI") == "1" else p.DIRECT)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(1.0 / HZ)
    p.loadURDF("plane.urdf")
    robot = p.loadURDF(URDF, [0, 0, Z0], globalScaling=SCALE, useFixedBase=False)
    for link in range(-1, p.getNumJoints(robot)):
        p.changeVisualShape(robot, link, rgbaColor=COLOR)
    if FIX_BASE:      # robot "colgado": ideal para visualizar real-to-sim sin que se caiga
        p.createConstraint(robot, -1, -1, -1, p.JOINT_FIXED, [0, 0, 0], [0, 0, 0], [0, 0, Z0])

    joints = []
    for j in range(p.getNumJoints(robot)):
        info = p.getJointInfo(robot, j)
        if info[2] == p.JOINT_REVOLUTE and info[8] < info[9]:
            joints.append((j, info[8], info[9]))
    groups = [joints[k::3] for k in range(3)]
    print(f"[sim-{NAME}] {URDF}: {len(joints)} articulaciones, grupos={[len(g) for g in groups]}, UDP :{PORT}")

    threading.Thread(target=rx_thread, daemon=True).start()
    mq = MetricsPublisher(f"sim-{NAME}")
    steps, t_pub, nxt, n = 0, time.monotonic(), time.monotonic(), 0
    while True:
        if n % 8 == 0:                                   # control a 30 Hz
            with lock:
                v, age = list(cmd["v"]), time.monotonic() - cmd["t"]
            for g, val in zip(groups, v):
                frac = max(0.0, min(1.0, val / 4095.0))
                for j, lo, hi in g:
                    p.setJointMotorControl2(robot, j, p.POSITION_CONTROL, targetPosition=lo + (hi - lo) * frac, force=50)
        p.stepSimulation()
        n += 1
        steps += 1
        nxt += 1.0 / HZ
        d = nxt - time.monotonic()
        if d > 0:
            time.sleep(d)
        elif d < -0.1:
            nxt = time.monotonic()
        now = time.monotonic()
        if now - t_pub >= 1.0:
            with lock:
                snap = stats.snapshot()
            mq.publish({**snap, "sim_hz": round(steps / (now - t_pub), 1), "cmd_age_s": round(age, 2),
                        "joints": len(joints), "bad_packets": cmd["bad"], "urdf": URDF})
            steps, t_pub = 0, now


if __name__ == "__main__":
    main()
