import logging
import paho.mqtt.client as mqtt
from sense_hat import SenseHat
import numpy as np
import time
import uuid
from datetime import datetime as dt
import auth0_handlers as auth0
import os

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    logger = logging.getLogger()
    logger.info("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("pylisium/home/%s/control"%(client.id))

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
    mag = sense.get_magnetometer_raw()
    return {
        "pressure": pressure,
        "temperature": np.mean(temp_press, temp_hum),
        "acceleration_x": acc["x"],
        "acceleration_y": acc["y"],
        "acceleration_z": acc["z"],
        "magnetic": mag
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
            "time": dt.utcnow(),
            "fields": reading
        }
    ]
    return meas

if __name__ == "__main__":
    # Initializes default python logger
    FORMAT = '[%(levelname)s] %(asctime)s - %(message)s'
    logging.basicConfig(format=FORMAT)
    LOGGER = logging.getLogger()
    LOGGER.setLevel(logging.INFO)
    # Initializes the MQTT client
    client_id = uuid.uuid4()
    client = mqtt.Client(client_id=client_id)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.connect("iot.pylisium.com", 1883, 60)
    client.loop_start()
    # Access the Rpi Hat for getting the sensors
    sense = SenseHat()
    sense.clear()
    # Tries to get a valid JWT
    token = auth0.get_token(
        os.environ.get("AUTH0_URI"),
        os.environ.get("AUTH0_CLIENT_ID"),
        os.environ.get("AUTH0_CLIENT_SECRET"),
        os.environ.get("AUTH0_AUDIENCE")
    )
    if token is not None:
        auth = {"username": "JWT", "password": token["access_token"]}
    else:
        auth = {"username": "JWT", "password": "mqtt"}
    try:
        while True:

            meas = create_measurement()
            client.publish(
                topic="pylisium/home/%s/environment"%(client_id),
                payload=meas,
                qos=2,
                client_id=client_id,
                auth=auth)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping script...")
        client.loop_stop()
        client.disconnect()