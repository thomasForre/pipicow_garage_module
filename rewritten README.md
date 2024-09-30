# CS50x Final project

I'm into smart house and I like building and programming my own devices.
I had an idea that I would like to control my garage door locally without depending on a cloud service.

After some reasearch I found out that a _Raspberry Pi Pico W_ was what I was looking for.
The _Raspberry Pi Pico W_ is capable of doing multiple things with it's GPIO's so I thought I would add more hardware to it
so I also could control lights in the garage, log temperature, humidity and atmospheric pressure, install limit switches to get
feedback from the garage door and a laser sensor to prevent the door from closing if an obstruction is detected.

This is my CS50x final project!

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
- One ```3.3 V relay``` is installed to trigger door operation, Start/Stop.
- One ```12 V relay``` to control signal from laser sensor.
- One ```24 V relay``` is installed to detect if door is moving. The door opener is providing a 24 V signal while door is moving.

### Breadboards, wiring and small parts:
Breadboards, wires, leds, resistors and other small parts to build the hardware is bought mostly from Aliexpress.


## Software
The _Raspberry Pi Pico W_ is installed with a main python file (main.py) that I've developed.
The code and functions are written by me but I had chatGPT to convert the code into a class structure that helped me understand classes better
and is now something I'll prefer to use for future projects. <br>

The program will start automatically as soon as the microcontroller in connected to a 5 V power source.
It will start its ```__init__``` method from the class which initializes neccecary pins, flags and handlers, connects to WIFI and MQTT broker, synchronize time with a NTP server
and schedule tasks like publishing values via MQTT and flashing leds every given interval of seconds.
I've set the led flashing function to run every 5 seconds to indicate that the system is running and publishing garage door state and BME280 values every 60 seconds.
The garage door state is also immediately published as soon as it changes state.

Some additional prewritten libraries are imported to use some of the installed hardware.

Prewritten libraries I've used:
- ```umqtt.simple```
- ```bme280```
- ```micropython schedule```

In addition I've imported a prewitten class for over the air update found here: [OTA](https://github.com/kevinmcaleer/ota). <br>
I've modified the class a bit to suit my project better.

### MQTT:
MQTT (Message Queuing Telemetry Transport) is used to send commands to and receive values and feedback from the microcontroller.
In ```main.py``` there is a MQTT callback function that subscribes to a given topic. The function has 3 different actions based on its input command.

#### Over the air update command:
I've set up a local HTTP-server at my home computer. If I would like to update the main.py I can instead of connecting the device to mye computer by cable send an "over-the-air" update command.
If such command is recieved by the MQTT callback funtion the program starts downloading the updated main.py from a given path on my server computer.
If successfull, the microcontroller will restart and run the newly installed program.

#### Door trigger command:
If the message to the MQTT subscription topic contains a door trigger command, the microcontroller will send a 3.3 V signal to its defined GPIO which will pulse the door trigger relay for 500 ms and start/stop the opening/closing of the garage door based on the garage door openers internal circuit.

#### Request BME280 values command:
The temperature, humidity and pressure values from the BME280 are published every 60 seconds by schedule, but can be requested manually if needed by sending a BME request command. If such command is received by the MQTT callback function the function will then immediately publish the values to the given MQTT topic.






