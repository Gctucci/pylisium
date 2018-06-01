import logging
import uuid
import paho.mqtt.client as mqtt
import os
from influxdb import InfluxDBClient
from threading import Timer
import auth0_handlers as auth0

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    logger = logging.getLogger()
    logger.info("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("pylisium/home/#/environment")

def on_disconnect(client, userdata, rc):
    logger = logging.getLogger()
    logger.info("Successfully disconnected from Broker...")

def on_message(client, userdata, message, db_client):
    logger = logging.getLogger()
    logger.info("Got message: %s", message)
    db_client.write_points([message.payload])
    logger.info("Stored message in InfluxDB database")

def connect_database():
    logger = logging.getLogger()
    client = InfluxDBClient(
        host=os.environ.get('INFLUXDB_HOST'),
        port=int(os.environ.get('INFLUXDB_PORT')),
        username=os.environ.get('INFLUXDB_USER'),
        password=os.environ.get('INFLUXDB_USER_PASSWORD'),
        database=os.environ.get('INFLUXDB_DB')
        )
    logger.info("Connected to InfluxDB database...")
    try:
        client.create_retention_policy(
            'expiry_policy',
            str(os.environ.get("INFLUXDB_RETENTION")),
            1,
            os.environ.get('INFLUXDB_DB'),
            True
        )
        logger.info("Created retention policy!")
    except Exception as e:
        logger.error(e)
        logger.warning("Error while trying to connect to database.")
    return client

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
    # Initializes default python logger
    FORMAT = '[%(levelname)s] %(asctime)s - %(message)s'
    logging.basicConfig(format=FORMAT)
    LOGGER = logging.getLogger()
    LOGGER.setLevel(logging.INFO)
    # Connects to the Influx Database
    db_client = connect_database()
    # Initializes the MQTT client
    CLIENT_ID = str(uuid.uuid4().int)
    client = mqtt.Client(client_id=CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = lambda client, userdata, message: on_message(client, userdata, message, db_client)
    client.on_disconnect = on_disconnect
    client.enable_logger(LOGGER)
    token = get_auth_token()
    client.username_pw_set(username="JWT",password=os.environ.get("MQTT_ACCESS_TOKEN"))
    client.connect(
        os.environ.get('MQTT_BROKER_HOST'),
        int(os.environ.get('MQTT_BROKER_PORT')),
        60
    )
    try:
        # Blocking call that processes network traffic, dispatches callbacks and
        # handles reconnecting.
        # Other loop*() functions are available that give a threaded interface and a
        # manual interface.
        client.loop_forever()
    except KeyboardInterrupt:
        print("Stopping script...")
        client.disconnect()
        db_client.close()
