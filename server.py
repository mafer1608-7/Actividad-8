"""track-server (VLAN1): servidor de pista PyBullet headless con API WebSocket.
Cada 'player' envía steer/throttle; si un jugador deja de enviar, su coche pasa a piloto automático."""
import asyncio
import json
import math
import os
import time

import pybullet as p
import pybullet_data
import websockets

from common.mqtt_util import MetricsPublisher

HZ = 240
WS_PORT = int(os.getenv("WS_PORT", "8765"))
N_CARS = 3
RX, RY, N_WP = 10.0, 6.0, 48          # pista elíptica: semiejes y nº de waypoints
MAX_WHEEL_VEL, FORCE = 40.0, 20.0
INPUT_TIMEOUT = 1.0                    # s sin comandos -> AUTO
WHEELS, STEER = [2, 3, 5, 7], [4, 6]   # joints de racecar/racecar.urdf


def waypoint(i):
    t = 2 * math.pi * (i % N_WP) / N_WP
    return RX * math.cos(t), RY * math.sin(t)


class Track:
    def __init__(self):
        p.connect(p.GUI if os.getenv("GUI") == "1" else p.DIRECT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.81)
        p.setTimeStep(1.0 / HZ)
        p.loadURDF("plane.urdf")
        vs = p.createVisualShape(p.GEOM_SPHERE, radius=0.15, rgbaColor=[1, 1, 1, 1])
        for k in range(N_WP):                      # marcas de la pista (visibles con GUI=1)
            x, y = waypoint(k)
            p.createMultiBody(0, -1, vs, [x, y, 0.05])
        self.cars, self.cmd, self.gain, self.last_input, self.mode = [], {}, {}, {}, {}
        for i in range(N_CARS):
            k = i * (N_WP // N_CARS)
            (x, y), (nx, ny) = waypoint(k), waypoint(k + 1)
            yaw = math.atan2(ny - y, nx - x)
            car = p.loadURDF("racecar/racecar.urdf", [x, y, 0.1], p.getQuaternionFromEuler([0, 0, yaw]))
            self.cars.append(car)
            pid = i + 1
            self.cmd[pid], self.gain[pid], self.last_input[pid], self.mode[pid] = (0.0, 0.0), 1.0, 0.0, "AUTO"

    def set_color(self, pid, rgb):
        car = self.cars[pid - 1]
        rgba = list(rgb) + [1]
        for link in range(-1, p.getNumJoints(car)):
            p.changeVisualShape(car, link, rgbaColor=rgba)

    def on_message(self, d):
        pid = int(d["player"])
        if pid not in self.cmd:
            return
        if "gain" in d:
            self.gain[pid] = float(d["gain"])
        if d.get("color") and d["color"] != getattr(self, f"_c{pid}", None):
            setattr(self, f"_c{pid}", d["color"])
            self.set_color(pid, d["color"])
        if not d.get("idle"):
            self.cmd[pid] = (max(-1, min(1, float(d["steer"]))), max(-1, min(1, float(d["throttle"]))))
            self.last_input[pid] = time.monotonic()

    def autopilot(self, car):
        (x, y, _), orn = p.getBasePositionAndOrientation(car)
        yaw = p.getEulerFromQuaternion(orn)[2]
        j = min(range(N_WP), key=lambda k: (waypoint(k)[0] - x) ** 2 + (waypoint(k)[1] - y) ** 2)
        tx, ty = waypoint(j + 3)
        err = math.atan2(ty - y, tx - x) - yaw
        err = math.atan2(math.sin(err), math.cos(err))
        return max(-1.0, min(1.0, err * 1.5)), 0.5

    def apply_controls(self):
        now = time.monotonic()
        for pid, car in enumerate(self.cars, start=1):
            if now - self.last_input[pid] < INPUT_TIMEOUT:
                steer, thr = self.cmd[pid]
                self.mode[pid] = "HUMAN"
            else:
                steer, thr = self.autopilot(car)
                self.mode[pid] = "AUTO"
            v = thr * self.gain[pid] * MAX_WHEEL_VEL
            for w in WHEELS:
                p.setJointMotorControl2(car, w, p.VELOCITY_CONTROL, targetVelocity=v, force=FORCE)
            for s in STEER:
                p.setJointMotorControl2(car, s, p.POSITION_CONTROL, targetPosition=steer * 0.5)


async def sim_loop(track, mq):
    steps, t_pub, nxt = 0, time.monotonic(), time.monotonic()
    n = 0
    while True:
        if n % 4 == 0:
            track.apply_controls()
        p.stepSimulation()
        n += 1
        steps += 1
        nxt += 1.0 / HZ
        delay = nxt - time.monotonic()
        if delay < -0.1:
            nxt = time.monotonic()
        await asyncio.sleep(max(0.0, delay))
        now = time.monotonic()
        if now - t_pub >= 1.0:
            cars = {}
            for pid, car in enumerate(track.cars, start=1):
                pos = p.getBasePositionAndOrientation(car)[0]
                cars[f"player-{pid}"] = {"mode": track.mode[pid], "x": round(pos[0], 2), "y": round(pos[1], 2)}
            mq.publish({"sim_hz": round(steps / (now - t_pub), 1), "cars": cars, "jitter_ms": None, "age_s": None})
            steps, t_pub = 0, now


async def main():
    track = Track()
    mq = MetricsPublisher("track-server")

    async def handler(ws):
        async for msg in ws:
            try:
                track.on_message(json.loads(msg))
            except Exception as e:
                print("mensaje inválido:", e)

    async with websockets.serve(handler, "0.0.0.0", WS_PORT):
        print(f"[track-server] WebSocket en :{WS_PORT}, {N_CARS} coches")
        await sim_loop(track, mq)


if __name__ == "__main__":
    asyncio.run(main())
