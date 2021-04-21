"""This uses the CLUE as a Bluetooth LE sensor node."""

from struct import *
import time
from adafruit_clue import clue
import adafruit_ble_broadcastnet

print("This is BroadcastNet CLUE sensor:", adafruit_ble_broadcastnet.device_address)
count = 0
measurement = adafruit_ble_broadcastnet.AdafruitSensorMeasurement()
count = 0
while True:
    if count >= 256:
        count = 0
    measurement.temperature = clue.temperature - 12
    measurement.pressure = clue.pressure / 10 + 12.7
    measurement.relative_humidity = clue.humidity
    # measurement.acceleration = clue.acceleration
    # measurement.magnetic = clue.magnetic
    measurement.sequence_number = count
    print('Measurement:\n', measurement)
    adafruit_ble_broadcastnet.broadcast(measurement)
    time.sleep(60)
    count += 1