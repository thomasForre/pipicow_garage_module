# Connect Raspberry PiPicoW to WIFI and MQTT

import sys
import time
import bme280
import asyncio
import secrets
import schedule
from otaUpdater import *
from machine import Pin, I2C, WDT, Timer
from umqtt.simple import MQTTClient
from connections import *

# Need to pull relay trigger low initially???

hassUsername = secrets.hassUsername
hassPassword = secrets.hassPassword

# Defining pins
i2c=I2C(0,sda=Pin(0), scl=Pin(1), freq=400000) #              BOARD INDEX 1 & 2 // BME280 (pressure, temperature, humitidy) 
switchDoorOpen = Pin(3, Pin.IN, Pin.PULL_DOWN)   #            BOARD INDEX 5     // Limit switch OPEN
switchDoorClosed = Pin(4, Pin.IN, Pin.PULL_DOWN) #            BOARD INDEX 6     // Limit switch CLOSED
relayDoorMoving = Pin(7, Pin.IN, Pin.PULL_DOWN) #             BOARD INDEX 10    // Door moving sensor
switchDoorObstructed = Pin(8, Pin.IN, Pin.PULL_DOWN) #        BOARD INDEX 11    // Throug-beam obstruction sensor
realyDoorTrigger = Pin(6, Pin.OUT, Pin.PULL_UP, value=1) #    BOARD INDEX 09    // Relay to trigger door, initialized to HIGH since relay is active LOW
sensorPIR = Pin(9, Pin.IN, Pin.PULL_DOWN) #                   BOARD INDEX 12    // PIR motion sensor

ledAlive = Pin(12, mode=Pin.OUT)  # -------B-L-U-E-------     BOARD INDEX 16    // LED for system alive
ledInternal = Pin("LED", Pin.OUT) # ---I-N-T-E-R-N-A-L---     BOARD INDEX N/A   // Internal LED on PiPicoW

async def blinkLed(led, nTimes, periodMs):
    # Toggle led nTimes for periodMs milliseconds
    blinkSpeed = periodMs / 1000
    for i in range(nTimes):
        led.toggle()
        await asyncio.sleep(blinkSpeed)
        led.toggle()
        if i == nTimes - 1:
            return
        await asyncio.sleep(blinkSpeed)

# Flash LEDs on boot
ledInternal.value(0)
ledAlive.value(0)
asyncio.run(blinkLed(ledInternal, 1, 500))
asyncio.run(blinkLed(ledAlive, 1, 500))

# Initialize flags for door status
doorStateOpen = bool(switchDoorOpen.value())
doorStateMoving = bool(relayDoorMoving.value())
doorStateClosed = bool(switchDoorClosed.value())
doorStateObstructed = bool(switchDoorObstructed.value())
        
def perfectDateTime():
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    now = time.localtime()
    weekDay = DAYS[now[6]]
    sec = str.format("{:02d}", now[5])
    min =str.format("{:02d}",  now[4])
    hours = str.format("{:02d}", now[3])
    day = str.format("{:02d}", now[2])
    month = str.format("{:02d}", now[1])
    year = str(now[0])
    
    timeString = hours + ":" + min + ":" + sec
    dateString = day + "." + month + "." + year
    
    # Output example: Fri 26.01.2024 @ 08:57:15
    return weekDay + " " + dateString + " @ " + timeString


def writeToLog(logString):
    with open("log.txt", "a") as logFile:
        logFile.write(perfectDateTime() + "\n")
        logFile.write("   " + logString + "\n")
    return


try:
    wifiConnect()
except RuntimeError as err:
    writeToLog(str(err.args[0]) + str(err.args[1]))
    machine.reset()

# Start MQTT section
mqttServer = secrets.hassServer
client_id = 'PiPicoW'
subscriptionTopic = "pipicow"

# MQTT callback function
def mqttSubscriptionCallback(topic, message):
    # Update command
    if "OTA" in message:
        client.publish("pipicow/info", "Update command recieved...")
        if ota_updater.download_and_install_update_if_available():
            client.publish("pipicow/info", "Code updated, resetting machine...")
            time.sleep(0.25)
            machine.reset()
            return
    # Door trigger command
    else:
        realyDoorTrigger.value(0)
        client.publish("pipicow/info", "door relay pulse")
        time.sleep(0.5)
        realyDoorTrigger.value(1)
        return


# MQTT connect
def mqttConnect():
    client = MQTTClient(client_id, mqttServer, port=1883, user=hassUsername, password=hassPassword, keepalive=3600)
    client.set_callback(mqttSubscriptionCallback)
    client.connect()
    client.subscribe(subscriptionTopic)
    print('Connected to %s MQTT Broker'%(mqttServer))
    print('Subscribed to topic: "%s"'%(subscriptionTopic))
    print(f"Subscribed to topic {subscriptionTopic}")
    return client


# MQTT reconnect
def mqttReconnect():
    print('Failed to connect to the MQTT Broker. Reconnecting...')
    time.sleep(5)
    machine.reset()
    
try:
    print("Connecting to MQTT broker...")
    client = mqttConnect()
    print("Done!")
    asyncio.run(blinkLed(ledAlive, 2, 50))
except OSError as e:
    mqttReconnect()
# End MQTT section


# Handler section

# OPEN door
def doorOpenHandler(pin):
    time.sleep_ms(100)
    global doorStateClosed
    doorStateClosed = False
    global doorStateMoving
    doorStateMoving = False
#     global doorStateObstructed
#     doorStateObstructed = False

    global doorStateOpen
    if not doorStateOpen:
        doorStateOpen = True
        client.publish("pipicow/doorState", "open")


# CLOSED door
def doorClosedHandler(pin):
    time.sleep_ms(100)
    
    global doorStateOpen
    doorStateOpen = False
    global doorStateMoving
    doorStateMoving = False
#     global doorStateObstructed
#     doorStateObstructed = False

    global doorStateClosed
    if not doorStateClosed:
        doorStateClosed = True
        client.publish("pipicow/doorState", "closed")


# MOVING door
def doorMovingHandlerRising(pin):
    time.sleep_ms(1000)
    
    print(pin.value())
    
    global doorStateOpen
    doorStateOpen = False
    global doorStateClosed
    doorStateClosed = False
    
    global doorStateMoving
    if not doorStateMoving:
        doorStateMoving = True
        client.publish("pipicow/doorState", "moving")
    else:
        doorStateMoving = False
        client.publish("pipicow/doorState", "stopped")
        
        
# OBSTRUCTED door
def doorObstructedHandler(pin):
    time.sleep_ms(100)
    global doorStateObstructed
    if not doorStateObstructed:
        doorStateObstructed = True
        client.publish("pipicow/doorState", "obstructed")
        return True
#     else:
#         print(f"Obstructed = {switchDoorObstructed.value()}")
#         doorStateObstructed = True
#         client.publish("pipicow/doorState", "obstructed")
#         return True
    

# PIR sensor
def sensorPirHandler(pin):
    time.sleep_ms(100) # Debounce time
    if sensorPIR.value():
        client.publish("pipicow/pir", "motion")

# End handler section


# MAIN
def publishBmeValues():
    bme = bme280.BME280(i2c=i2c)
    client.publish("pipicow/bme280/temperature", bme.values[0])
    client.publish("pipicow/bme280/pressure", bme.values[1])
    client.publish("pipicow/bme280/humidity", bme.values[2])


def publishDoorState():
    client.publish("pipicow/doorStateOpen", str(switchDoorOpen.value()))
    client.publish("pipicow/doorStateClosed", str(switchDoorClosed.value()))
    client.publish("pipicow/doorStateMoving", str(relayDoorMoving.value()))
    client.publish("pipicow/doorStateObstructed", str(switchDoorObstructed.value()))
    

def flashLeds():
    ledAlive.toggle()
    ledInternal.toggle()
    time.sleep(0.05)
    ledAlive.toggle()
    ledInternal.toggle()


async def main():
    while True:
        # Checking for incomming mqtt commands
        client.check_msg()
        
        schedule.run_pending()
        
        await asyncio.sleep(1)

# Publish values at start-up
publishBmeValues()
publishDoorState()

schedule.every(5).seconds.do(flashLeds)
schedule.every(10).seconds.do(publishBmeValues)
schedule.every(60).seconds.do(publishDoorState)

# IRQ
switchDoorOpen.irq(trigger=Pin.IRQ_RISING, handler=doorOpenHandler)
switchDoorClosed.irq(trigger=Pin.IRQ_RISING, handler=doorClosedHandler)
relayDoorMoving.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=doorMovingHandlerRising)
switchDoorObstructed.irq(trigger=Pin.IRQ_RISING, handler=doorObstructedHandler)
sensorPIR.irq(trigger=Pin.IRQ_RISING, handler=sensorPirHandler)

asyncio.run(main())

