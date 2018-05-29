import http.client
import logging
import time
import math
import json

# Initializes default python logger
FORMAT = '[%(levelname)s] %(asctime)s - %(message)s'
logging.basicConfig(format=FORMAT)
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

def get_token(uri_conn, client_id, client_secret, audience, max_retries=5):
    logger = logging.getLogger()

    conn = http.client.HTTPSConnection(uri_conn)
    payload = "{\"client_id\":\"%s\",\"client_secret\":\"%s\",\"audience\":\"%s\",\"grant_type\":\"client_credentials\"}"%(client_id, client_secret, audience)

    headers = { 'content-type': "application/json" }
    logger.info("Getting Auth token...")
    retries = 0
    while retries < max_retries:
        try:
            conn.request("POST", "/oauth/token", payload, headers)

            res = conn.getresponse()
            data = res.read()
            logger.info("Got response: %s", data.decode("utf-8"))
            return json.loads(data.decode("utf-8"))
        except Exception as e:
            logger.warning("Could not connect to Auth API, trying again...")
            retries += 1
            # Sleeps for an amount equivalent to the number of retries
            time.sleep(1*math.pow(retries, 0.5))
    return None

def validate_token(api_path, token={}, max_retries=5):
    logger = logging.getLogger()

    if "token_type" not in token.keys() and "access_token" not in token.keys():
        logger.warning("Token without keys 'token_type' and/or 'access_token'. "
                        "Found only %s keys"%list(token.keys()))
    else:
        conn = http.client.HTTPConnection(api_path)
        headers = { 'authorization': "{token_type} {access_token}".format(**token) }
        retries = 0
        logger.info("Validating given token...")
        while retries < max_retries:
            try:
                conn.request("GET", "/", headers=headers)

                res = conn.getresponse()
                data = res.read()
                logger.info("Got response: %s", data.decode("utf-8"))
                resp = json.loads(data.decode("utf-8"))

            except Exception as e:
                logger.warning("Could not connect to Auth API, trying again...")
                retries += 1
                # Sleeps for an amount equivalent to the number of retries
                time.sleep(1*math.pow(retries, 0.5))
    return None
get_token("pylisium.auth0.com", "6sbknlPRs2cIirnzrQwkfA3rlCwTPuhx",
    "exdtYmWp-uGIxa8McipEaXTrgnmKk3Iu4pq8ic7fZa40IvNZXN6bAJ0Q-eob0iXn",
    "https://iot.broker.pylisium.com")