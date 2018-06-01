import logging
import paho.mqtt.client as mqtt
from sense_hat import SenseHat
import numpy as np
import time
import uuid
from datetime import datetime as dt
from threading import Timer
import os
import auth0_handlers as auth0
import json
import threading
import queue

def load_env(fname=".env", sep="=="):
    logger = logging.getLogger()
    with open(fname, "r") as f:
        for line in f.readlines():
            envs = line.split(sep)
            if len(envs) >= 2:
                logger.info("Setting env variable %s", line)
                os.environ[envs[0]] = envs[-1].strip("\n")


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    logger = logging.getLogger()
    logger.info("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("".join(["pylisium/home/control/", client._client_id.decode("utf-8")]))

def on_disconnect(client, userdata, rc):
    logger = logging.getLogger()
    logger.info("Successfully disconnected from Broker...")

def on_message(client, userdata, message):
    logger = logging.getLogger()
    logger.info("Got message: %s", message)

def get_reading():
    pressure = sense.get_pressure()
    temp_press = sense.get_temperature_from_pressure()
    temp_hum = sense.get_temperature_from_humidity()
    acc = sense.get_accelerometer_raw()
    mag = sense.get_compass_raw()
    orient = sense.get_orientation()
    return {
        "pressure": pressure,
        "temperature": float(temp_press + temp_hum) / 2,
        "humidity": sense.get_humidity(),
        "acceleration_x": acc["x"],
        "acceleration_y": acc["y"],
        "acceleration_z": acc["z"],
        "compass_x": mag["x"],
        "compass_y": mag["y"],
        "compass_z": mag["z"],
        "pitch": orient["pitch"],
        "roll": orient["roll"],
        "yaw": orient["yaw"]
        }

def create_measurement():
    reading = get_reading()
    meas = [
        {
            "measurement": "environment",
            "tags": {
                "device_type": "sense_hat",
                "device_id": os.environ.get("DEVICE_ID")
            },
            "time": dt.utcnow().isoformat(),
            "fields": reading
        }
    ]
    return meas

def get_auth_token():
    token = auth0.get_token(
        os.environ.get("AUTH0_URI"),
        os.environ.get("AUTH0_CLIENT_ID"),
        os.environ.get("AUTH0_CLIENT_SECRET"),
        os.environ.get("AUTH0_AUDIENCE")
    )
    # Tries to get a valid JWT
    if token is not None:
        os.environ["MQTT_ACCESS_TOKEN"]  = token["access_token"]
        if "expires_in" in token.keys():
            # Set a timer to renew the token
            renew_token = Timer(int(token["expires_in"]), get_auth_token)
            renew_token.start()
    else:
        os.environ["MQTT_ACCESS_TOKEN"]  = "mqtt"
    return token

def display_text(sense):
    global CUR_MEAS
    while True:
        temp_msg = "Temp.: %s"%(round(CUR_MEAS[0]["fields"]["humidity"], 1))
        hum_msg = "Hum.: %s"%(round(CUR_MEAS[0]["fields"]["humidity"], 1))
        sense.show_message( temp_msg + " - " + hum_msg, scroll_speed=(0.04))
        sense.clear()
        time.sleep(1)

def send_data(client, topic):
    global MEASUREMENTS
    logger = logging.getLogger()
    logger.info("Start publishing on topic %s", topic)
    client.loop_start()
    while True:
        item = MEASUREMENTS.get()
        if item is None:
            logger.info("Measurement queue is empty")
        else:
            client.publish(
                topic=str(topic),
                payload=json.dumps(item)
            )
            logger.info("Published data: %s", item)
            MEASUREMENTS.task_done()
            time.sleep(1)


if __name__ == "__main__":
    global CUR_MEAS
    global MEASUREMENTS
    MEASUREMENTS = queue.Queue()
    CUR_MEAS = [{"fields": {"temperature": 0, "humidity": 0}}]
    load_env()
    # Initializes default python logger
    FORMAT = '[%(levelname)s] %(asctime)s - %(message)s'
    logging.basicConfig(format=FORMAT)
    LOGGER = logging.getLogger()
    LOGGER.setLevel(logging.INFO)
    # Initializes the MQTT client
    client_id = str(uuid.uuid4().int)
    client = mqtt.Client(client_id=client_id)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.enable_logger(LOGGER)
    token = get_auth_token()
    client.username_pw_set(username="JWT",password=os.environ.get("MQTT_ACCESS_TOKEN"))
    client.connect_async(os.environ.get("MQTT_BROKER_HOST"), int(os.environ.get("MQTT_BROKER_PORT")))
    topic = "".join(["pylisium/home/environment/", client_id])
    # Access the Rpi Hat for getting the sensors
    sense = SenseHat()
    sense.low_light = True
    sense.clear()
    thread_display = threading.Thread(target=display_text, args=(sense, ) )
    thread_mqtt = threading.Thread(target=send_data, args=(client, topic, ) )
    thread_display.start()
    thread_mqtt.start()
    try:
        while True:
            auth = {"username": "JWT", "password": os.environ.get("MQTT_ACCESS_TOKEN")}
            meas = create_measurement()
            MEASUREMENTS.put(meas)
            CUR_MEAS = meas
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping script...")
        sense.clear()
        client.loop_stop()
        client.disconnect()
        thread_display.join(timeout=5)
        thread_mqtt.join(timeout=5)