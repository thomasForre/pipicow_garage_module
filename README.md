# pipicow_garage

This code is installed on a Raspberry Pi Pico who is mounted in the garage
for controlling lights and garage door and logging.

HARDWARE

BME280:
Installed to log temperature, pressure and humidity in the garage.

PIR sensor:
Control lights in the garage.

Limit switches:
To get door position feedback,  Open/Closed

Through beam sensor (laser):
Laser sensor to detect obstructions for the door to prevent remote operation if door is obstructed.

Relays:
One 3.3 V is installed to trigger door operation, Start/Stop.
One 12 V relay to control signal from laser sensor.
One 24 V relay is installed to detect if door is moving. The door opener is providing a 24 V signal while door is moving.


