FROM python:3.4-alpine
ADD ../../pyhome /code
WORKDIR /code/pyhome/mqtt_persist
RUN pip3 install -r requirements.txt
CMD ["python3", "mqtt_persist.py"]