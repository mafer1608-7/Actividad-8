// ESP32 MAESTRA: lee 3 potenciómetros y los envía por UDP al contenedor que controla (real-to-sim).
//   CMD,<id>,<seq>,<millis>,<v1>,<v2>,<v3>   @50 Hz  -> HOST_IP:CMD_PORT   (contenedor player/sim)
//   HB,<id>,<seq>,<millis>                    @10 Hz  -> HOST_IP:9999       (plano de administración)
// Cableado: potenciómetros (3.3V - cursor - GND) en GPIO34, GPIO35, GPIO32.
//   Coches: v1 = dirección (centro = recto), v2 = acelerador.   Robots: v1..v3 = 3 grupos de articulaciones.
#include <WiFi.h>
#include <WiFiUdp.h>
#include "secrets.h"

#ifndef DEVICE_ID
#define DEVICE_ID "ctrl-1"
#endif
#ifndef CMD_PORT
#define CMD_PORT 5001
#endif
#define HB_PORT 9999
#define CMD_PERIOD_MS 20
#define HB_PERIOD_MS 100
const uint8_t PIN_A = 34, PIN_B = 35, PIN_C = 32, PIN_LED = 2;

WiFiUDP udp;
uint32_t seqCmd = 0, seqHb = 0;
unsigned long lastCmd = 0, lastHb = 0;

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);                 // menos jitter
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("[%s] conectando a %s", DEVICE_ID, WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) { delay(300); Serial.print('.'); }
  Serial.printf("\n[%s] IP %s -> %s:%d\n", DEVICE_ID, WiFi.localIP().toString().c_str(), HOST_IP, CMD_PORT);
}

int readAvg(uint8_t pin) {              // promedio de 4 lecturas para filtrar ruido
  int s = 0;
  for (int i = 0; i < 4; i++) s += analogRead(pin);
  return s / 4;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  analogReadResolution(12);
  connectWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) { digitalWrite(PIN_LED, LOW); connectWifi(); }
  digitalWrite(PIN_LED, HIGH);
  unsigned long now = millis();
  char buf[96];

  if (now - lastCmd >= CMD_PERIOD_MS) {
    lastCmd += CMD_PERIOD_MS;
    if (now - lastCmd >= CMD_PERIOD_MS) lastCmd = now;   // recuperar si nos atrasamos
    int n = snprintf(buf, sizeof(buf), "CMD,%s,%lu,%lu,%d,%d,%d", DEVICE_ID, (unsigned long)seqCmd++, now,
                     readAvg(PIN_A), readAvg(PIN_B), readAvg(PIN_C));
    udp.beginPacket(HOST_IP, CMD_PORT);
    udp.write((const uint8_t*)buf, n);
    udp.endPacket();
  }
  if (now - lastHb >= HB_PERIOD_MS) {
    lastHb += HB_PERIOD_MS;
    if (now - lastHb >= HB_PERIOD_MS) lastHb = now;
    int n = snprintf(buf, sizeof(buf), "HB,%s,%lu,%lu", DEVICE_ID, (unsigned long)seqHb++, now);
    udp.beginPacket(HOST_IP, HB_PORT);
    udp.write((const uint8_t*)buf, n);
    udp.endPacket();
  }
}
