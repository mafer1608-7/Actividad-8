"""player-N (VLAN1): cliente de la pista. Recibe UDP de su ESP32 maestra y lo reenvía al track-server por WebSocket."""
import asyncio
import json
import os
import time

import websockets

from common.jitter import StreamStats
from common.mqtt_util import MetricsPublisher

PID = int(os.getenv("PLAYER_ID", "1"))
UDP_PORT = int(os.getenv("UDP_PORT", "5000"))
URL = os.getenv("TRACK_URL", "ws://track-server:8765")
COLOR = [float(c) for c in os.getenv("CAR_COLOR", "0,0,1").split(",")]
STYLE = os.getenv("CAR_STYLE", "sport")
GAIN = {"sport": 1.0, "classic": 0.7, "drift": 1.2}.get(STYLE, 1.0)

stats = StreamStats()
state = {"v": None, "t": 0.0, "ws": False, "bad": 0}


class UdpIn(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        try:
            p = data.decode().strip().split(",")        # CMD,id,seq,ms,v1,v2,v3
            if p[0] != "CMD":
                return
            stats.update(int(p[2]), int(p[3]))
            state["v"], state["t"] = (int(p[4]), int(p[5])), time.monotonic()
        except Exception:
            state["bad"] += 1


def conv(v1, v2):
    steer = (v1 - 2048) / 2048.0
    steer = 0.0 if abs(steer) < 0.05 else steer
    return max(-1.0, min(1.0, steer)), max(0.0, min(1.0, v2 / 4095.0))


async def ws_loop():
    while True:
        try:
            async with websockets.connect(URL) as ws:
                state["ws"] = True
                while True:
                    await asyncio.sleep(1 / 30)
                    msg = {"player": PID, "color": COLOR, "style": STYLE, "gain": GAIN}
                    if state["v"] and time.monotonic() - state["t"] < 0.5:
                        msg["steer"], msg["throttle"] = conv(*state["v"])
                    else:
                        msg["idle"] = True
                    await ws.send(json.dumps(msg))
        except Exception as e:
            state["ws"] = False
            print("[player] sin conexión con track-server:", e)
            await asyncio.sleep(1)


async def metrics_loop():
    mq = MetricsPublisher(f"player-{PID}")
    while True:
        await asyncio.sleep(1)
        mq.publish({**stats.snapshot(), "ws_connected": state["ws"], "bad_packets": state["bad"], "style": STYLE})


async def main():
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(UdpIn, local_addr=("0.0.0.0", UDP_PORT))
    print(f"[player-{PID}] UDP :{UDP_PORT} -> {URL} color={COLOR} estilo={STYLE}")
    await asyncio.gather(ws_loop(), metrics_loop())


if __name__ == "__main__":
    asyncio.run(main())
