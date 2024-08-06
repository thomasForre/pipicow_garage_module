# pipicow_garage

This code is under developing.
The hardware and software is tested and working but is far from optimal.
The project has been paused for some time due to necessary priorities.
All required files are not yet provided in this repository.
Code and readme will be updated ...


This code (main.py) is installed on a Raspberry Pi Pico who is mounted in my garage
for controlling lights and garage door and logging.


## HARDWARE

### Microcontroller:
Raspberry Pi Pico W (RP2040)

### BME280:
Installed to log temperature, pressure and humidity in the garage.

### PIR sensor:
To detect motion for controlling lights in the garage.

### Limit switches:
To get door position feedback,  Open/Closed

### Through-beam sensor (laser):
Laser sensor to detect obstructions for the door to prevent remote operation if door is obstructed.

### Relays:

One 3.3 V is installed to trigger door operation, Start/Stop.
One 12 V relay to control signal from laser sensor.
One 24 V relay is installed to detect if door is moving. The door opener is providing a 24 V signal while door is moving.

## SOFTWARE

The program starts automatically when the Raspberry Pi Pico is powered up.
It connects to WIFI and MQTT broker before it starts publishing BME values and door state via MQTT.
The program has a MQTT callback function. If the function receives a MQTT message including the string "OTA" it starts over the air update
from eighter github repository or local HTTP-server. Other messages will trigger the door relay to open/stop/close the garage door.

Every 5 seconds:   Flash LEDs

Every 10 seconds:  Publish BME values over MQTT

Every 60 seconds:  Publish door state

Door states (open / closed / moving / obstructed) and PIR sensor state
are updated using interrups request (IRQ) on rising pins.
