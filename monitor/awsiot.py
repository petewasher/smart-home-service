from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import json
import Queue
import threading
import logging

# Configure logging
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.INFO)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)
class AWSIoTUpdater(object):
    def __init__(self, config):
        self.root_ca = config['aws_iot']['certs']['root_ca']
        self.priv_key = config['aws_iot']['certs']['priv_key']
        self.cert = config['aws_iot']['certs']['cert']

        self.endpoint = config['aws_iot']['endpoint']
        self.client_id = config['aws_iot']['client']
        self.topic = config['aws_iot']['topic']

        self.room = config['sensor_location']
        self.measurement = config['aws_iot']['measurement_name']

        self.client = None

        self.queue = Queue.Queue()
        self.process_thread = threading.Thread(target=self.process)
        self.halt_event = threading.Event()

    def process(self):
        while not self.halt_event.isSet():
            try:
                reading = self.queue.get(timeout=1)
                payload = {
                    "room": self.room,
                    self.measurement: reading
                }

                logger.info("Deliver: %s", payload)

                try:
                    result = self._publish(payload)
                    logger.info("Delivery result: %s", result)
                except Exception, ex:
                    print ex

            except Queue.Empty:
                pass

    def connect(self):
        self.client = AWSIoTMQTTClient(self.client_id)
        self.client.configureCredentials(
            self.root_ca,
            self.priv_key,
            self.cert
        )

        self.client.configureEndpoint(self.endpoint, 8883)

        # Setup params
        self.client.configureAutoReconnectBackoffTime(1, 32, 20)
        self.client.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
        self.client.configureDrainingFrequency(2)  # Draining: 2 Hz
        self.client.configureConnectDisconnectTimeout(10)  # 10 sec
        self.client.configureMQTTOperationTimeout(5) # 5 sec

        # Connect
        self.client.connect()

    def _publish(self, payload):

        outgoing_payload = json.dumps(payload)
        return self.client.publish(self.topic, outgoing_payload, 1)

    def disconnect(self):
        self.client.disconnect()

    def prepare(self):
        self.connect()
        self.process_thread.start()

    def stop(self):
        self.halt_event.set()
        self.process_thread.join()
        self.disconnect()


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
