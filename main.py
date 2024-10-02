"""
Connect Raspberry Pi PicoW to WIFI and MQTT
Publish temperature, humidity and pressure
Publish garage door state

Main.py rewritten to a class structure by chatGT
"""

# import logging                           # <-- Start use logger instead of using the write_to_log function
import sys 
import time
import bme280
import asyncio
import secrets
import ntptime
import schedule
from otaUpdater import *                    # <-- remember to update name casing to snake_case
from machine import Pin, I2C, Timer
from umqtt.simple import MQTTClient
from connections import *


class RaspberryPiPicoW:
    def __init__(self):
        # Initialize MQTT parameters and pins
        self.hass_username = secrets.hassUsername
        self.hass_password = secrets.hassPassword
        self.mqtt_server = secrets.hassServer
        self.client_id = 'PiPicoW'
        self.subscription_topic = "pipicow"

        self.i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)
        self.initialize_pins()
        self.initialize_flags()

        # Flash LEDs on boot
        asyncio.run(self.blink_led(self.led_internal, 1, 500))
        asyncio.run(self.blink_led(self.led_alive, 1, 500))

        try:
            wifiConnect()                                            # <-- remember to update name casing to snake_case
        except RuntimeError as err:
            print("Failed to connect to WIFI, resetting machine...")
            self.write_to_log(str(err.args[0]) + str(err.args[1]))
            machine.reset()

        # Synchronize time with an NTP server
        self.sync_time()

        # Connect to MQTT
        self.client = self.mqtt_connect()

        # Set up handlers for GPIO interrupts
        self.setup_handlers()

        # Decide interval for tasks (seconds) and schedule tasks
        self.flash_leds_interval = 5
        self.publish_bme_interval = 60
        self.publish_door_state_interval = 60
        self.schedule_tasks()

    
    def sync_time(self):
        try:
            # Synchronize the time with an NTP server
            ntptime.settime()
            self.write_to_log("Time synchronized successfully.")
            print("Time synchronized successfully.")
            return True
        except Exception as err:
            self.write_to_log(f"Failed to synchronize time: {err}")
            print("Failed to synchronize time:", err)
            return False

    def initialize_pins(self):
        self.switch_door_open = Pin(3, Pin.IN, Pin.PULL_DOWN)
        self.switch_door_closed = Pin(4, Pin.IN, Pin.PULL_DOWN)
        self.relay_door_moving = Pin(7, Pin.IN, Pin.PULL_DOWN)
        self.switch_door_obstructed = Pin(8, Pin.IN, Pin.PULL_DOWN)
        self.relay_door_trigger = Pin(6, Pin.OUT, Pin.PULL_UP, value=1)
        self.sensor_pir = Pin(9, Pin.IN, Pin.PULL_DOWN)
        self.led_alive = Pin(12, mode=Pin.OUT)
        self.led_internal = Pin("LED", Pin.OUT)
    
    def initialize_flags(self):
        self.door_state_open = False
        self.door_state_closed = False
        self.door_state_moving = False
        self.door_state_obstructed = False
    
    def setup_handlers(self):
        self.switch_door_open.irq(trigger=Pin.IRQ_RISING, handler=self.door_open_handler)
        self.switch_door_closed.irq(trigger=Pin.IRQ_RISING, handler=self.door_closed_handler)
        self.relay_door_moving.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.door_moving_handler)
        self.switch_door_obstructed.irq(trigger=Pin.IRQ_RISING, handler=self.door_obstructed_handler)
        self.sensor_pir.irq(trigger=Pin.IRQ_RISING, handler=self.sensor_pir_handler)

    async def blink_led(self, led, n_times, period_ms):
        blink_speed = period_ms / 1000
        for i in range(n_times):
            led.toggle()
            await asyncio.sleep(blink_speed)
            led.toggle()
            if i == n_times - 1:
                return
            await asyncio.sleep(blink_speed)

    def write_to_log(self, log_string):
        with open("log.txt", "a") as log_file:
            log_file.write(self.perfect_date_time() + "\n")
            log_file.write("   " + log_string + "\n")

    def perfect_date_time(self):
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        now = time.localtime()
        week_day = days[now[6]]
        seconds = str.format("{:02d}", now[5])
        minutes = str.format("{:02d}", now[4])
        hours = str.format("{:02d}", now[3])
        day = str.format("{:02d}", now[2])
        month = str.format("{:02d}", now[1])
        year = str(now[0])

        time_string = f"{hours}:{minutes}:{seconds}"
        date_string = f"{day}.{month}.{year}"

        return f"{week_day} {date_string} {time_string}"

    def mqtt_subscription_callback(self, topic, message):
        if "OTA" in message:
            self.client.publish("pipicow/info", "Update command received...")
            # try:
            if ota_updater.download_and_install_update_if_available():
                self.client.publish("pipicow/info", "Code updated, resetting machine...")
                print("Code updated, resetting machine...")
                time.sleep_ms(500)
                machine.reset()
        elif "door" in message:
            self.relay_door_trigger.value(0)
            self.client.publish("pipicow/info", "Door relay pulse")
            time.sleep_ms(500) # Time to hold relay closed
            self.relay_door_trigger.value(1)
        elif "BME" in message:
            if self.publish_bme_values():
                self.client.publish("pipicow/info", "BME request succeeded")
            else:
                self.client.publish("pipicow/info", "BME request failed")
        else:
            self.client.publish("pipicow/info", "Unknown mqtt command")

    def mqtt_connect(self):
        max_attempts = 5
        attempt = 0
        print("Connecting to MQTT broker...")
        
        while attempt < max_attempts:
            client = MQTTClient(self.client_id, self.mqtt_server, port=1883, user=self.hass_username, password=self.hass_password, keepalive=3600)
            try:
                client.set_callback(self.mqtt_subscription_callback)
                client.connect()
                print(f"Connected to {self.mqtt_server} MQTT Broker")
                client.subscribe(self.subscription_topic)
                print(f"Subscribed to topic: {self.subscription_topic}")
                
                return client
            except Exception as err:
                print(f"Connection attempt {attempt + 1} failed: {err}")
                print("Retrying in 3 seconds...")
                attempt += 1
                time.sleep(3)

        print(f"Max MQTT connection attempts reached ({max_attempts}), resetting machine in 3 seconds...")
        time.sleep(3)
        machine.reset()
            
    def mqtt_reconnect(self):
        print("Failed to connect to the MQTT Broker. Reconnecting...")
        time.sleep(5)
        self.client = self.mqttConnect()

    def publish_bme_values(self):
        try:
            bme = bme280.BME280(i2c=self.i2c) # Initialize the BME sensor
            self.client.publish("pipicow/bme280/temperature", bme.values[0])
            self.client.publish("pipicow/bme280/pressure", bme.values[1])
            self.client.publish("pipicow/bme280/humidity", bme.values[2])
            return True
        except Exception as err:
            self.write_to_log(f"Error publishing BME values: {err}")
            print("Failed to publish BME values", err)
            return False

    def publish_door_state(self):
        self.client.publish("pipicow/doorStateOpen", str(self.switch_door_open.value()))
        self.client.publish("pipicow/doorStateClosed", str(self.switch_door_closed.value()))
        self.client.publish("pipicow/doorStateMoving", str(self.relay_door_moving.value()))
        self.client.publish("pipicow/doorStateObstructed", str(self.switch_door_obstructed.value()))

    def flash_leds(self):
        self.led_alive.toggle()
        self.led_internal.toggle()
        time.sleep_ms(50)
        self.led_alive.toggle()
        self.led_internal.toggle()

    def schedule_tasks(self):
        schedule.every(self.flash_leds_interval).seconds.do(self.flash_leds)
        schedule.every(self.publish_bme_interval).seconds.do(self.publish_bme_values)
        schedule.every(self.publish_door_state_interval).seconds.do(self.publish_door_state)

    def door_open_handler(self, pin):
        time.sleep_ms(100)
        self.door_state_closed = False
        self.door_state_moving = False
        if not self.door_state_open:
            self.door_state_open = True
            self.client.publish("pipicow/doorState", "open")        # <-- Change topic to snake_case

    def door_closed_handler(self, pin):
        time.sleep_ms(100)
        self.door_state_open = False
        self.door_state_moving = False
        if not self.door_state_closed:
            self.door_state_closed = True
            self.client.publish("pipicow/doorState", "closed")        # <-- Change topic to snake_case

    def door_moving_handler(self, pin):
        time.sleep_ms(1000)
        self.door_state_open = False
        self.door_state_closed = False
        if not self.door_state_moving:
            self.door_state_moving = True
            self.client.publish("pipicow/doorState", "moving")        # <-- Change topic to snake_case
        else:
            self.door_state_moving = False
            self.client.publish("pipicow/doorState", "stopped")        # <-- Change topic to snake_case

    def door_obstructed_handler(self, pin):
        time.sleep_ms(100)
        if not self.door_state_obstructed:
            self.door_state_obstructed = True
            self.client.publish("pipicow/doorState", "obstructed")    """ <-- Change topic to snake_case """

    def sensor_pir_handler(self, pin):
        time.sleep_ms(100)
        if self.sensor_pir.value():
            self.client.publish("pipicow/pir", "motion")

    async def main(self):
        while True:
            self.client.check_msg()
            schedule.run_pending()
            await asyncio.sleep(1)

if __name__ == "__main__":
    # Create an instance of the RaspberryPiPicoW class and start main
    pico_device = RaspberryPiPicoW()
    pico_device.publish_bme_values()
    pico_device.publish_door_state()
    asyncio.run(pico_device.main())
