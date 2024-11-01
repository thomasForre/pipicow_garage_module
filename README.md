# PiPiCoW Garage Module
### CS50x Final Project
<br>

> [Project presentation video](https://www.youtube.com/)<br>
> Presentation video is not yet created...


#### Description:
I'm into smart house, and I love building and programming my own devices.
I had an idea that I wanted to make my garage door smart and control it locally without depending on an expensive cloud service.

After some research, I found out that a _Raspberry Pi Pico W_ was what I was looking for. I could have made a quick and dirty solution with a
wireless relay connected to my garage door opener, but the _Raspberry Pi Pico W_ is capable of doing so much more than that with its GPIOs.
So I decided to add more hardware to the microcontroller so that I also could do actions based on a motion sensor, log temperature, humidity and atmospheric pressure,
read states of limit switches to get feedback from the garage door and a laser sensor to prevent remote operation if an obstruction is detected.

This is my CS50x final project!
 

## Hardware

### Microcontroller:
Raspberry Pi Pico W (RP2040)

### BME280 sensor:
Installed to log temperature, pressure and humidity in the garage.

### PIR sensor:
A passive infrared sensor is installed to detect motion for controlling lights in the garage or do other things based on motion detection.

### Limit switches:
Two mechanical limit switches, one for open and one for closed to get door position feedback (Open/Closed)

### Through-beam sensor (laser):
Laser sensor to detect obstructions for the door to prevent remote operation if door is obstructed.

### Relays:
- One ```3.3 V relay``` is installed to trigger door operation, Start/Stop.
- One ```12 V relay``` to control signal from laser sensor.
- One ```24 V relay``` is installed to detect if door is moving. The door opener is providing a 24 V signal while door is moving.

### Breadboards, wiring and small parts:
Breadboards, wires, leds, resistors, and other small parts to build the hardware is bought mostly from Aliexpress.

The microcontroller is powered from a 12 V source on the garage door opener which is stepped down to 5 V.

## Software
The _Raspberry Pi Pico W_ is installed with a main python file (main.py) that I've developed.
The code and functions are written by me but I had chatGPT to convert the code into a class structure that helped me understand classes better
and is now something I'll prefer to use for future projects. <br>

The program will start automatically as soon as the microcontroller is connected to a 5 V power source.
It will start its ```__init__``` method from the class which initializes necessary pins, flags and handlers, connects to WIFI and MQTT broker, synchronize time with a NTP server
and schedule tasks like publishing values via MQTT and flashing LEDs every given interval of seconds.
I've set the LED flashing function to run every 5 seconds to indicate that the system is running and publishing garage door state and BME280 values every 60 seconds.
The garage door state is also immediately published as soon as it changes state.

Some additional pre-written libraries are imported to use some of the installed hardware.

Pre-written libraries I've used:
- ```umqtt.simple```
- ```bme280```
- ```micropython schedule```

In addition I've imported a pre-witten class for over the air update found here: [OTA](https://github.com/kevinmcaleer/ota). <br>
I've modified the class a bit to suit my project better.

### MQTT
MQTT (Message Queuing Telemetry Transport) is used to send commands to and receive values and feedback from the microcontroller.
In ```main.py``` there is a MQTT callback function that subscribes to a specific topic. The function has 3 different actions based on its input command.

#### Over the air update command:
I've set up a local HTTP server at my home computer. If I would like to update the main.py I can instead of connecting the device to my computer by cable, send an "over-the-air" update command.
If such command is recieved by the MQTT callback function, the program starts downloading the updated main.py from a given path on my server computer. If successful, the microcontroller will restart and run the newly installed program.

#### Door trigger command:
If the message to the MQTT subscription topic contains a door trigger command, the microcontroller will send a 3.3 V signal to its defined GPIO which will pulse the door trigger relay for 500 ms to start/stop the opening/closing of the garage door based on the garage door opener's internal circuit.

#### Request BME280 values command:
The temperature, humidity and pressure values from the BME280 are published every 60 seconds by schedule, but can be requested manually if needed by sending a BME request command. If such command is received by the MQTT callback function the function will then immediately publish the values to the given MQTT topic.

All commands publish information that the command is received. Other than the three predefined commands are ignored followed by a MQTT message notifying the user that it's an unknown MQTT command.






