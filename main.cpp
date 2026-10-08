// ESP32 ESCLAVA (VLAN3): se suscribe a lab/status/<contenedor> y refleja el estado en LEDs.
//   UP = encendido fijo | DEGRADED = parpadeo 2 Hz | DOWN = apagado
//   Sin MQTT = todos parpadean rápido (5 Hz).  Sin mensajes >5 s para un contenedor = DOWN.
// Cableado: GPIO -> resistencia 220 ohm -> LED -> GND
#include <WiFi.h>
#include <PubSubClient.h>
#include "secrets.h"

const int N = 7;
const char* NAMES[N] = {"track-server", "player-1", "player-2", "player-3", "sim-nao", "sim-spot", "sim-pepper"};
const uint8_t PINS[N] = {13, 14, 16, 17, 18, 19, 21};
enum State { S_DOWN, S_UP, S_DEGRADED };
State st[N];
unsigned long lastSeen[N];

WiFiClient wifi;
PubSubClient mqtt(wifi);
unsigned long lastTry = 0;

void onMsg(char* topic, byte* payload, unsigned int len) {
  const char* name = strrchr(topic, '/');
  if (!name) return;
  name++;
  String p; for (unsigned int i = 0; i < len; i++) p += (char)payload[i];
  for (int i = 0; i < N; i++) {
    if (strcmp(name, NAMES[i]) == 0) {
      st[i] = p == "UP" ? S_UP : (p == "DEGRADED" ? S_DEGRADED : S_DOWN);
      lastSeen[i] = millis();
    }
  }
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < N; i++) { pinMode(PINS[i], OUTPUT); st[i] = S_DOWN; lastSeen[i] = 0; }
  for (int i = 0; i < N; i++) { digitalWrite(PINS[i], HIGH); delay(120); digitalWrite(PINS[i], LOW); }  // prueba de LEDs
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  mqtt.setServer(HOST_IP, MQTT_PORT);
  mqtt.setCallback(onMsg);
}

void loop() {
  unsigned long now = millis();
  if (WiFi.status() == WL_CONNECTED && !mqtt.connected() && now - lastTry > 2000) {
    lastTry = now;
    if (mqtt.connect("led-monitor")) { mqtt.subscribe("lab/status/#"); Serial.println("MQTT ok"); }
  }
  mqtt.loop();
  bool link = mqtt.connected();
  for (int i = 0; i < N; i++) {
    bool on;
    if (!link) on = (now / 100) % 2;
    else {
      State s = (lastSeen[i] && now - lastSeen[i] < 5000) ? st[i] : S_DOWN;
      on = s == S_UP ? true : (s == S_DEGRADED ? (now / 250) % 2 : false);
    }
    digitalWrite(PINS[i], on);
  }
}
