"""Utilidades MQTT compatibles con paho-mqtt 1.x y 2.x."""
import json
import os
import time

import paho.mqtt.client as mqtt


def make_client(client_id):
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
    except AttributeError:               # paho 1.x
        return mqtt.Client(client_id=client_id)


class MetricsPublisher:
    """Publica métricas JSON en metrics/<name> hacia el broker del plano de administración."""

    def __init__(self, name):
        self.name = name
        host = os.getenv("MQTT_HOST", "192.168.30.10")
        port = int(os.getenv("MQTT_PORT", "1883"))
        self.client = make_client(f"{name}-metrics")
        self.client.reconnect_delay_set(1, 5)
        self.client.connect_async(host, port, keepalive=10)
        self.client.loop_start()

    def publish(self, data):
        payload = dict(data, name=self.name, ts=time.time())
        self.client.publish(f"metrics/{self.name}", json.dumps(payload), qos=0)
