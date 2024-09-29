# Connect Raspberry Pi PicoW to WIFI and MQTT
# Rewritten original file into a class by chatGPT 29.09.24

import sys
import time
import bme280
import asyncio
import secrets
import schedule
from otaUpdater import *
from machine import Pin, I2C, Timer
from umqtt.simple import MQTTClient
from connections import *

class RaspberryPiPicoW:
    def __init__(self):
        # Initialize pins and MQTT parameters
        self.hassUsername = secrets.hassUsername
        self.hassPassword = secrets.hassPassword
        self.mqttServer = secrets.hassServer
        self.client_id = 'PiPicoW'
        self.subscriptionTopic = "pipicow"

        self.i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)
        self.initialize_pins()
        self.initialize_flags()

        # Flash LEDs on boot
        self.blink_led(self.ledInternal, 1, 500)
        self.blink_led(self.ledAlive, 1, 500)

        try:
            wifiConnect()
        except RuntimeError as err:
            self.write_to_log(str(err.args[0]) + str(err.args[1]))
            machine.reset()

        self.client = self.mqtt_connect()

        # Set up handlers for GPIO interrupts
        self.setup_handlers()

        # Schedule tasks
        self.schedule_tasks()

    def initialize_pins(self):
        self.switchDoorOpen = Pin(3, Pin.IN, Pin.PULL_DOWN)
        self.switchDoorClosed = Pin(4, Pin.IN, Pin.PULL_DOWN)
        self.relayDoorMoving = Pin(7, Pin.IN, Pin.PULL_DOWN)
        self.switchDoorObstructed = Pin(8, Pin.IN, Pin.PULL_DOWN)
        self.relayDoorTrigger = Pin(6, Pin.OUT, Pin.PULL_UP, value=1)
        self.sensorPIR = Pin(9, Pin.IN, Pin.PULL_DOWN)
        self.ledAlive = Pin(12, mode=Pin.OUT)
        self.ledInternal = Pin("LED", Pin.OUT)

    def initialize_flags(self):
        self.doorStateOpen = False
        self.doorStateClosed = False
        self.doorStateMoving = False
        self.doorStateObstructed = False

    async def blink_led(self, led, nTimes, periodMs):
        blinkSpeed = periodMs / 1000
        for i in range(nTimes):
            led.toggle()
            await asyncio.sleep(blinkSpeed)
            led.toggle()
            if i == nTimes - 1:
                return
            await asyncio.sleep(blinkSpeed)

    def write_to_log(self, logString):
        with open("log.txt", "a") as logFile:
            logFile.write(self.perfect_date_time() + "\n")
            logFile.write("   " + logString + "\n")

    def perfect_date_time(self):
        DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        now = time.localtime()
        weekDay = DAYS[now[6]]
        sec = str.format("{:02d}", now[5])
        min = str.format("{:02d}", now[4])
        hours = str.format("{:02d}", now[3])
        day = str.format("{:02d}", now[2])
        month = str.format("{:02d}", now[1])
        year = str(now[0])

        timeString = hours + ":" + min + ":" + sec
        dateString = day + "." + month + "." + year
        return weekDay + " " + dateString + " @ " + timeString

    def mqtt_subscription_callback(self, topic, message):
        if "OTA" in message:
            self.client.publish("pipicow/info", "Update command received...")
            if ota_updater.download_and_install_update_if_available():
                self.client.publish("pipicow/info", "Code updated, resetting machine...")
                time.sleep(0.25)
                machine.reset()
        else:
            self.relayDoorTrigger.value(0)
            self.client.publish("pipicow/info", "door relay pulse")
            time.sleep(0.5)
            self.relayDoorTrigger.value(1)

    def mqtt_connect(self):
        client = MQTTClient(self.client_id, self.mqttServer, port=1883, user=self.hassUsername, password=self.hassPassword, keepalive=3600)
        client.set_callback(self.mqtt_subscription_callback)
        client.connect()
        client.subscribe(self.subscriptionTopic)
        print(f'Connected to {self.mqttServer} MQTT Broker')
        print(f'Subscribed to topic: "{self.subscriptionTopic}"')
        return client

    def setup_handlers(self):
        self.switchDoorOpen.irq(trigger=Pin.IRQ_RISING, handler=self.door_open_handler)
        self.switchDoorClosed.irq(trigger=Pin.IRQ_RISING, handler=self.door_closed_handler)
        self.relayDoorMoving.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.door_moving_handler)
        self.switchDoorObstructed.irq(trigger=Pin.IRQ_RISING, handler=self.door_obstructed_handler)
        self.sensorPIR.irq(trigger=Pin.IRQ_RISING, handler=self.sensor_pir_handler)

    def publish_bme_values(self):
        bme = bme280.BME280(i2c=self.i2c)
        self.client.publish("pipicow/bme280/temperature", bme.values[0])
        self.client.publish("pipicow/bme280/pressure", bme.values[1])
        self.client.publish("pipicow/bme280/humidity", bme.values[2])

    def publish_door_state(self):
        self.client.publish("pipicow/doorStateOpen", str(self.switchDoorOpen.value()))
        self.client.publish("pipicow/doorStateClosed", str(self.switchDoorClosed.value()))
        self.client.publish("pipicow/doorStateMoving", str(self.relayDoorMoving.value()))
        self.client.publish("pipicow/doorStateObstructed", str(self.switchDoorObstructed.value()))

    def flash_leds(self):
        self.ledAlive.toggle()
        self.ledInternal.toggle()
        time.sleep(0.05)
        self.ledAlive.toggle()
        self.ledInternal.toggle()

    def schedule_tasks(self):
        schedule.every(5).seconds.do(self.flash_leds)
        schedule.every(10).seconds.do(self.publish_bme_values)
        schedule.every(60).seconds.do(self.publish_door_state)

    async def main(self):
        while True:
            self.client.check_msg()
            schedule.run_pending()
            await asyncio.sleep(1)

    def door_open_handler(self, pin):
        time.sleep_ms(100)
        self.doorStateClosed = False
        self.doorStateMoving = False
        if not self.doorStateOpen:
            self.doorStateOpen = True
            self.client.publish("pipicow/doorState", "open")

    def door_closed_handler(self, pin):
        time.sleep_ms(100)
        self.doorStateOpen = False
        self.doorStateMoving = False
        if not self.doorStateClosed:
            self.doorStateClosed = True
            self.client.publish("pipicow/doorState", "closed")

    def door_moving_handler(self, pin):
        time.sleep_ms(1000)
        self.doorStateOpen = False
        self.doorStateClosed = False
        if not self.doorStateMoving:
            self.doorStateMoving = True
            self.client.publish("pipicow/doorState", "moving")
        else:
            self.doorStateMoving = False
            self.client.publish("pipicow/doorState", "stopped")

    def door_obstructed_handler(self, pin):
        time.sleep_ms(100)
        if not self.doorStateObstructed:
            self.doorStateObstructed = True
            self.client.publish("pipicow/doorState", "obstructed")

    def sensor_pir_handler(self, pin):
        time.sleep_ms(100)
        if self.sensorPIR.value():
            self.client.publish("pipicow/pir", "motion")

if __name__ == "__main__":
    # Create an instance of the RaspberryPiPicoW class and start main
    pico_device = RaspberryPiPicoW()
    pico_device.publish_bme_values()
    pico_device.publish_door_state()
    asyncio.run(pico_device.main())
