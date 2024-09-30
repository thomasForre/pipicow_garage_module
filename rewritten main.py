# Connect Raspberry Pi PicoW to WIFI and MQTT
# Publish temperature, humidity and pressure
# Publish garage door state

# Main.py rewritten to a class structure by chatGTP

import sys
import time
import bme280
import asyncio
import secrets
import ntptime
import schedule
from otaUpdater import *
from machine import Pin, I2C, Timer
from umqtt.simple import MQTTClient
from connections import *

class RaspberryPiPicoW:
    def __init__(self):
        # Initialize MQTT parameters and pins
        self.hassUsername = secrets.hassUsername
        self.hassPassword = secrets.hassPassword
        self.mqttServer = secrets.hassServer
        self.client_id = 'PiPicoW'
        self.subscriptionTopic = "pipicow"

        self.i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)
        self.initializePins()
        self.initializeFlags()

        # Flash LEDs on boot
        asyncio.run(self.blinkLed(self.ledInternal, 1, 500))  # <-- Decide to use async blink or 
        asyncio.run(self.blinkLed(self.ledAlive, 1, 500))
        
        try:
            wifiConnect()
        except RuntimeError as err:
            print("Failed to connect to WIFI, resetting machine...")
            self.writeToLog(str(err.args[0]) + str(err.args[1]))
            machine.reset()

        # Synchronize time with an NTP server
        self.syncTime()

        # Connenct to MQTT
        self.client = self.mqttConnect()

        # Set up handlers for GPIO interrupts
        self.setupHandlers()

        # Decide interval for tasks (seconds) and schedule tasks
        self.flashLedsInterval = 5
        self.publishBmeInterval = 60
        self.publishDoorStateInterval = 60
        self.scheduleTasks()

    def syncTime():
        try:
            # Synchronize the time with an NTP server
            ntptime.settime()
            writeToLog(self, "Time synchronized successfully.")
            print("Time synchronized successfully.")
        except Exception as err:
            writeToLog(self, f"Failed to synchronize time: {err}")
            print("Failed to synchronize time:", err)
        
    def initializePins(self):
        self.switchDoorOpen = Pin(3, Pin.IN, Pin.PULL_DOWN)
        self.switchDoorClosed = Pin(4, Pin.IN, Pin.PULL_DOWN)
        self.relayDoorMoving = Pin(7, Pin.IN, Pin.PULL_DOWN)
        self.switchDoorObstructed = Pin(8, Pin.IN, Pin.PULL_DOWN)
        self.relayDoorTrigger = Pin(6, Pin.OUT, Pin.PULL_UP, value=1)
        self.sensorPIR = Pin(9, Pin.IN, Pin.PULL_DOWN)
        self.ledAlive = Pin(12, mode=Pin.OUT)
        self.ledInternal = Pin("LED", Pin.OUT)

    def initializeFlags(self):
        self.doorStateOpen = False
        self.doorStateClosed = False
        self.doorStateMoving = False
        self.doorStateObstructed = False

    async def blinkLed(self, led, nTimes, periodMs):  # <-- Use this blink function og flashLeds() ??
        blinkSpeed = periodMs / 1000
        for i in range(nTimes):
            led.toggle()
            await asyncio.sleep(blinkSpeed)
            led.toggle()
            if i == nTimes - 1:
                return
            await asyncio.sleep(blinkSpeed)

    def writeToLog(self, logString):
        with open("log.txt", "a") as logFile:
            logFile.write(self.perfectDateTime() + "\n")
            logFile.write("   " + logString + "\n")

    def perfectDateTime(self):
        DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        now = time.localtime()
        weekDay = DAYS[now[6]]
        seconds = str.format("{:02d}", now[5])
        minutes = str.format("{:02d}", now[4])
        hours = str.format("{:02d}", now[3])
        day = str.format("{:02d}", now[2])
        month = str.format("{:02d}", now[1])
        year = str(now[0])

        timeString = f"{hours}:{minutes}:{seconds}"
        dateString = f"{day}.{month}.{year}"
        
        # Output example: Fri 26.01.2024 08:57:15
        return f"{weekDay} {dateString} {timeString}"

    def mqttSubscriptionCallback(self, topic, message):
        if "OTA" in message:
            # Command for over the air update is received
            self.client.publish("pipicow/info", "Update command received...")
            if ota_updater.download_and_install_update_if_available():
                self.client.publish("pipicow/info", "Code updated, resetting machine...")
                print("Code updated, resetting machine...")
                time.sleep(0.25)
                machine.reset()
        elif "door" in message:
            self.relayDoorTrigger.value(0)
            self.client.publish("pipicow/info", "door relay pulse")
            time.sleep(0.5)
            self.relayDoorTrigger.value(1)
        elif "BME" in message:
            if self.publishBmeValues():
                self.client.publish("pipicow/info", 

    def mqttConnect(self):
        client = MQTTClient(self.client_id, self.mqttServer, port=1883, user=self.hassUsername, password=self.hassPassword, keepalive=3600)
        client.set_callback(self.mqttSubscriptionCallback)
        client.connect()
        client.subscribe(self.subscriptionTopic)
        print(f"Connected to {self.mqttServer} MQTT Broker")
        print(f"Subscribed to topic: {self.subscriptionTopic}")
        return client

    def setupHandlers(self):
        self.switchDoorOpen.irq(trigger=Pin.IRQ_RISING, handler=self.doorOpenHandler)
        self.switchDoorClosed.irq(trigger=Pin.IRQ_RISING, handler=self.doorClosedHandler)
        self.relayDoorMoving.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.doorMovingHandler)
        self.switchDoorObstructed.irq(trigger=Pin.IRQ_RISING, handler=self.doorObstructedHandler)
        self.sensorPIR.irq(trigger=Pin.IRQ_RISING, handler=self.sensorPirHandler)

    def publishBmeValues(self):
        bme = bme280.BME280(i2c=self.i2c)
        try:
            self.client.publish("pipicow/bme280/temperature", bme.values[0])
            self.client.publish("pipicow/bme280/pressure", bme.values[1])
            self.client.publish("pipicow/bme280/humidity", bme.values[2])
            return True
        except Exception as e:
            self.writeToLog(f"Error publishing BME values: {e}")
            return False

    def publishDoorState(self):
        self.client.publish("pipicow/doorStateOpen", str(self.switchDoorOpen.value()))
        self.client.publish("pipicow/doorStateClosed", str(self.switchDoorClosed.value()))
        self.client.publish("pipicow/doorStateMoving", str(self.relayDoorMoving.value()))
        self.client.publish("pipicow/doorStateObstructed", str(self.switchDoorObstructed.value()))

    def flashLeds(self):
        self.ledAlive.toggle()
        self.ledInternal.toggle()
        time.sleep(0.05)
        self.ledAlive.toggle()
        self.ledInternal.toggle()
    
    def scheduleTasks(self):
        schedule.every(self.flashLedsInterval).seconds.do(self.flashLeds)
        schedule.every(self.publishBmeInterval).seconds.do(self.publishBmeValues)
        schedule.every(self.publishDoorStateInterval).seconds.do(self.publishDoorState)

    def doorOpenHandler(self, pin):
        time.sleep_ms(100)
        self.doorStateClosed = False
        self.doorStateMoving = False
        if not self.doorStateOpen:
            self.doorStateOpen = True
            self.client.publish("pipicow/doorState", "open")

    def doorClosedHandler(self, pin):
        time.sleep_ms(100)
        self.doorStateOpen = False
        self.doorStateMoving = False
        if not self.doorStateClosed:
            self.doorStateClosed = True
            self.client.publish("pipicow/doorState", "closed")
            
    def doorMovingHandler(self, pin):
        time.sleep_ms(1000)
        self.doorStateOpen = False
        self.doorStateClosed = False
        if not self.doorStateMoving:
            self.doorStateMoving = True
            self.client.publish("pipicow/doorState", "moving")
        else:
            self.doorStateMoving = False
            self.client.publish("pipicow/doorState", "stopped")

    def doorObstructedHandler(self, pin):
        time.sleep_ms(100)
        if not self.doorStateObstructed:
            self.doorStateObstructed = True
            self.client.publish("pipicow/doorState", "obstructed")

    def sensorPirHandler(self, pin):
        time.sleep_ms(100)
        if self.sensorPIR.value():
            self.client.publish("pipicow/pir", "motion")

    async def main(self):
        while True:
            self.client.check_msg()
            schedule.run_pending()
            await asyncio.sleep(1)

if __name__ == "__main__":
    # Create an instance of the RaspberryPiPicoW class and start main
    picoDevice = RaspberryPiPicoW()
    picoDevice.publishBmeValues()
    picoDevice.publishDoorState()
    asyncio.run(picoDevice.main())
