from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import json

class AWSIoTUpdater(object):
    def __init__(self, config):
        self.root_ca = config['aws_iot']['certs']['root_ca']
        self.priv_key = config['aws_iot']['certs']['priv_key']
        self.cert = config['aws_iot']['certs']['cert']

        self.endpoint = config['aws_iot']['endpoint']
        self.client_id = config['aws_iot']['client']
        self.topic = config['aws_iot']['topic']

        self.client = None

    def connect(self):
        self.client = AWSIoTMQTTClient("downstairs_temperature")
        self.client.configureCredentials(
            self.root_ca,
            self.priv_key,
            self.cert
        )

        self.client.configureEndpoint(self.endpoint, 8883)
        self.client.connect()

    def publish(self, payload):

        outgoing_payload = json.dumps(payload)
        return self.client.publish(self.topic, outgoing_payload, 1)

    def disconnect(self):
        self.client.disconnect()

if __name__ == "__main__":
    config = {}
    with open("./config.json") as config_f:
        data = config_f.read()
        config = json.loads(data)

    updater = AWSIoTUpdater(config)
    updater.connect()
    updater.publish({
        "room": "downstairs",
        "temperature": 25.441
    })