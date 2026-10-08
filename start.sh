#!/bin/sh
mosquitto -c /app/admin/mosquitto.conf &
sleep 1
exec python3 /app/admin/monitor.py
