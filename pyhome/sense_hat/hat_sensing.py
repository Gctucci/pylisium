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
    return {
        "pressure": pressure,
        "temperature": float(temp_press + temp_hum) / 2,
        "humidity": sense.get_humidity(),
        "acceleration_x": acc["x"],
        "acceleration_y": acc["y"],
        "acceleration_z": acc["z"],
        "compass_x": mag["x"],
        "compass_y": mag["y"],
        "compass_z": mag["z"]
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


if __name__ == "__main__":
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
    LOGGER.info("Start publishing on topic %s", topic)
    client.loop_start()
    # Access the Rpi Hat for getting the sensors
    sense = SenseHat()
    sense.clear()
    try:
        while True:
            auth = {"username": "JWT", "password": os.environ.get("MQTT_ACCESS_TOKEN")}
            meas = create_measurement()
            client.publish(
                topic=str(topic),
                payload=json.dumps(meas)
            )
            LOGGER.info("Published data: %s", meas)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping script...")
        client.loop_stop()
        client.disconnect()