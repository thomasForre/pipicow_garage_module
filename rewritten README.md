# CS50x Final project
Some intro...

## Background
I'm into smart house and I like building and programming my own devices.
I had an idea that I would like to control my garage door locally without depending on a cloud service.

After some reasearch I found out that a _Raspberry Pi Pico W_ was what I was looking for.
The _Raspberry Pi Pico W_ is capable of doing multiple things with it's GPIO's so I thought I would add more hardware to it
so I also could control lights in the garage, log temperature, humidity and atmospheric pressure, install limit switches to get
feedback from the garage door and a laser sensor to prevent the door from closing if an obstruction is detected.


## Hardware

### Microcontroller:
Raspberry Pi Pico W (RP2040)

### BME280 sensor:
Installed to log temperature, pressure and humidity in the garage.

### PIR sensor:
A passive infrared sensor is installed to detect motion for controlling lights in the garage or do other things based on motion detection.

### Limit switches:
Two mechanical limit switches, one for open and one for closed to get door position feedback, Open/Closed

### Through-beam sensor (laser):
Laser sensor to detect obstructions for the door to prevent remote operation if door is obstructed.

### Relays:
- One 3.3 V is installed to trigger door operation, Start/Stop.
- One 12 V relay to control signal from laser sensor.
- One 24 V relay is installed to detect if door is moving. The door opener is providing a 24 V signal while door is moving.

##### Breadboards, wiring and small parts:
Breadboards, wires, leds, resistors and other small parts to build the hardware is bought mostly from Aliexpress.


## Software
The _Raspberry Pi Pico W_ is installed with a main python file I've developed. Some additional prewritten libraries
are also installed to use some of the installed hardware.

Prewritten libraries I've used:
- ```umqtt.simple```
- ```bme280```
- ```micropython schedule```

### MQTT:
MQTT (Message Queuing Telemetry Transport) is used to send commands to and receive values and feedback from the controller.
In ```main.py``` there is a MQTT callback function that subscribes to a given topic. The function has 3 different actions based on its input command.
#### Over the air update:
I've set up a local HTTP-server at my home. If an "over-the-air" update command is recieved by the MQTT callback funtion the program starts downloading
the updated code from a given path on my server computer.

#### Door trigger command:

#### Request BME280 values



