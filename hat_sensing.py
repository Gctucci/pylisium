import paho.mqtt.client as mqtt
from sense_hat import SenseHat
import numpy as np
import schedule
import time
from datetime import datetime as dt
import paho.mqtt.client as mqtt

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("$SYS/#")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print("Got message: "+msg.topic+" "+str(msg.payload))


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
            "time": dt.utcnow(),
            "fields": reading
        }
    ]
    return meas

if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("iot.eclipse.org", 1883, 60)
    client.loop_start()
    # Access the Rpi Hat for getting the sensors
    sense = SenseHat()
    sense.clear()
    try:
        while True:
            meas = create_measurement()
            client.publish("home/environment", meas)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping script...")
        client.loop_stop()
