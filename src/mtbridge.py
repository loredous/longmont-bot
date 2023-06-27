from queue import Queue
from typing import List
import paho.mqtt.client
import paho.mqtt.subscribe
from meshtastic.mqtt_pb2 import ServiceEnvelope as mqtt_message
from meshtastic.mesh_pb2 import User, Position
from meshtastic.telemetry_pb2 import Telemetry
import meshtastic.portnums_pb2 as portnums

class UserinfoMap(dict):
    def update_info(self, uid: str, info: dict):
        if not self.get(uid,None):
            self[uid] = {}
        self[uid].update(info)

class IncomingMeshtasticTextMessage():
    def __init__(self, userinfo: dict, message: str, timestamp: str, channel: str) -> None:
        self.userinfo = userinfo
        self.messsage = message
        self.timestamp = timestamp
        self.channel = channel

class MeshtasticBridge():
    def __init__(self, address: str, port: int = 1883, username: str = None, password: str = None) -> None:
        self.usermap = UserinfoMap()
        self._client = paho.mqtt.client.Client()
        if username and password:
            self._client.username_pw_set(username=username, password=password)
        self._pending_from_meshtastic = Queue()
        self._client.tls_set()
        
        self._client.on_message = self.handle_message
        self._client.on_connect = self.on_connect
        self._client.connect(host=address, port=port)
        self._client.subscribe('msh/2/c/#')

    def start_handling(self):
        self._client.loop_start()

    def stop_handling(self):
        self._client.loop_stop()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    def get_incoming_messages(self) -> List[IncomingMeshtasticTextMessage]:
        messages = []
        while not self._pending_from_meshtastic.empty():
            messages.append(self._pending_from_meshtastic.get())
        return messages

    def handle_text_message(self, message: mqtt_message):
        uid = str(message.packet.__getattribute__('from'))
        userinfo = self.usermap.get(uid, None)
        if not userinfo:
            userinfo = {"uid": uid}
        self._pending_from_meshtastic.put_nowait(
            IncomingMeshtasticTextMessage(
                userinfo=userinfo, 
                message=message.packet.decoded.payload.decode(),
                timestamp=str(message.packet.rx_time),
                channel=message.channel_id
            )
        )

    def handle_position_message(self, message: mqtt_message):
        uid = str(message.packet.__getattribute__('from'))
        position = Position()
        position.ParseFromString(message.packet.decoded.payload)
        position_info = {
            "latitude": position.latitude_i * 1e-7,
            "longitude": position.longitude_i * 1e-7,
            "altitude": f'{position.altitude}m',
            "pos_at_time": position.time,
            "uid": uid
        }
        self.usermap.update_info(uid, position_info)

    def handle_nodeinfo_message(self, message: mqtt_message):
        uid = str(message.packet.__getattribute__('from'))
        user = User()
        user.ParseFromString(message.packet.decoded.payload)
        userinfo = {
            "long_name": user.long_name,
            "short_name": user.short_name,
            "id": user.id,
            "hardware": user.hw_model,
            "uid": uid
        }
        self.usermap.update_info(uid, userinfo)

    def handle_telemetry_message(self, message: mqtt_message):
        uid = str(message.packet.__getattribute__('from'))
        telemetry = Telemetry()
        telemetry.ParseFromString(message.packet.decoded.payload)
        telemetryinfo = {
            "battery": telemetry.device_metrics.battery_level,
            "uid": uid
        }
        self.usermap.update_info(uid,telemetryinfo)

    def handle_message(self, client, userdata, message: paho.mqtt.client.MQTTMessage):
        mqt_message = mqtt_message()
        mqt_message.ParseFromString(message.payload)
        match mqt_message.packet.decoded.portnum:
            case portnums.TEXT_MESSAGE_APP:
                self.handle_text_message(mqt_message)
            case portnums.POSITION_APP:
                self.handle_position_message(mqt_message)
            case portnums.NODEINFO_APP:
                self.handle_nodeinfo_message(mqt_message)
            case portnums.TELEMETRY_APP:
                self.handle_telemetry_message(mqt_message)

if __name__ == "__main__":
    bridge = MeshtasticBridge('192.168.21.106')
    bridge.start_handling()
    while True:
        messages = bridge.get_incoming_messages()
        for message in messages:
            username = message.userinfo.get('short_name',message.userinfo.get('uid','Unknown'))
            print(f"{username}: {message.messsage}")