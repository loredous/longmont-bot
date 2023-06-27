FROM python:3-slim

ENV BOT_TOKEN=""
ENV MQTT_PASSWORD=""

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY src/ src/

WORKDIR /src

CMD [ "/usr/local/bin/python", "bot.py" ]