"""
Connect Raspberry Pi Pico W to WIFI and MQTT
Publish temperature, humidity and pressure via MQTT
Publish garage door state via MQTT

"""
import asyncio
import json
import logging
import ntptime
import time

import bme280
import schedule
from machine import Pin, I2C, Timer
from umqtt.simple import MQTTClient

import connections
import helpers
from ota_updater import *
import secrets

class RaspberryPiPicoW:
    def __init__(self):
       
        # Setup logging
        logging.basicConfig(filename="app.log",
                            level=logging.INFO,
                            format="%(asctime)s - %(levelname)s - %(message)s")
        
        # Synchronie time with an NTP server
        if helpers.sync_time():
            logging.info("Time sync successful")

        logging.info("RaspberryPiPicoW class initialized")
        
        # Initialize MQTT parameters and pins
        self.hass_username = secrets.hass_username
        self.hass_password = secrets.hass_password
        self.mqtt_server = secrets.hass_server
        self.client_id = 'PiPicoW'
        self.subscription_topic = "pipicow"
        
        # Initialize I2C for BME280 (temperature, humidity and pressure) Breadboard index 1 and 2
        self.i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)
        
        self.initialize_pins()
        self.initialize_flags()
        
        # Initialize LEDs to off and flash LEDs on boot
        self.led_alive.value(0)
        self.led_internal.value(0)
        asyncio.run(helpers.blink_led(self.led_internal, 1, 500))
        asyncio.run(helpers.blink_led(self.led_alive, 1, 500))

        # Connect to wifi
        try:
            connection_info = connections.wifi_connect()
            logging.info(f"Connected to {connection_info['ssid']} with IP {connection_info['device_ip']}")
        except RuntimeError as err:
            print(str(err.args[0]) + str(err.args[1]))
            print("Failed to connect to WIFI, resetting machine...")
#             logging.error(f"Failed to connect to WIFI: { err } Resetting machine...")
            machine.reset()
        
        # Connect to MQTT
        self.client = self.mqtt_connect()

        # Set up handlers for GPIO interrupts
        self.setup_handlers()
        
        # Decide interval for tasks (seconds) and schedule tasks
        self.flash_leds_interval = 5
        self.publish_bme_interval = 60
        self.publish_door_state_interval = 60
        self.schedule_tasks()
        
        self.last_door_trigger = 0


    def initialize_pins(self):
        self.switch_door_open = Pin(3, Pin.IN, Pin.PULL_DOWN)            # BOARD INDEX 5  | Limit switch OPEN
        self.switch_door_closed = Pin(4, Pin.IN, Pin.PULL_DOWN)          # BOARD INDEX 6  | Limit switch CLOSED
        self.relay_door_moving = Pin(7, Pin.IN, Pin.PULL_DOWN)           # BOARD INDEX 10 | Door moving sensor
        self.switch_door_obstructed = Pin(8, Pin.IN, Pin.PULL_DOWN)      # BOARD INDEX 11 | IR beam obstruction sensor
        self.relay_door_trigger = Pin(6, Pin.OUT, Pin.PULL_UP, value=1)  # BOARD INDEX 09 | Relay to trigger door, initialized to HIGH since relay is active LOW
        self.sensor_pir = Pin(9, Pin.IN, Pin.PULL_DOWN)                  # BOARD INDEX 12 | PIR motion sensor
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
    
    def set_last_trigger(self):
        self.last_door_trigger = time.time()
        return
        
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
            if self.last_door_trigger == 0 or self.last_door_trigger + 5 < time.time():
                self.relay_door_trigger.value(0)
                self.client.publish("pipicow/info", "Door relay pulse")
                # Time to hold relay closed
                time.sleep_ms(500)
                self.relay_door_trigger.value(1)
                
                self.set_last_trigger()
            else:
                self.client.publish("pipicow/info", "Too early dor command")
                return False                
            
            print(f"last_door_trigger, {self.last_door_trigger}")  
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

    def publish_bme_values(self):
        try:
            # Initialize the BME sensor
            bme = bme280.BME280(i2c=self.i2c)
            bmeData = {
                "temperature": bme.values[0],
                "pressure": bme.values[1],
                "humidity": bme.values[2]
            }
            self.client.publish("pipicow/bme280/data", json.dumps(bmeData))
            return True
        except Exception as err:
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
            self.client.publish("pipicow/door_state", "open")

    def door_closed_handler(self, pin):
        time.sleep_ms(100)
        self.door_state_open = False
        self.door_state_moving = False
        if not self.door_state_closed:
            self.door_state_closed = True
            self.client.publish("pipicow/door_state", "closed")

    def door_moving_handler(self, pin):
        time.sleep_ms(100)
        self.door_state_open = False
        self.door_state_closed = False
        if not self.door_state_moving:
            self.door_state_moving = True
            self.client.publish("pipicow/door_state", "moving")
#         else:
#             self.door_state_moving = False
#             self.client.publish("pipicow/door_state", "stopped")

    def door_obstructed_handler(self, pin):
        time.sleep_ms(100)
        if not self.door_state_obstructed:
            self.door_state_obstructed = True
            self.client.publish("pipicow/door_state", "obstructed")
                
    def sensor_pir_handler(self, pin):
        time.sleep_ms(100)
        if self.sensor_pir.value():
            self.client.publish("pipicow/pir", "motion")

    async def main(self):
        # Flash LEDs to indicate app start
        for i in range(5):
            self.flash_leds()
        print("Application running!")
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