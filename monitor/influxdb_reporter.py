import datetime
import Queue
import socket
import threading
from influxdb import InfluxDBClient

# Configure logging
import logging
logger = logging.getLogger("Monitor.InfluxReporter")
logger.setLevel(logging.INFO)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

class InfluxDBReporter(object):
    def __init__(self, config):
        self.client = InfluxDBClient(
            config["database"]["host"],
            config["database"]["port"],
            config["database"]["username"],
            config["database"]["password"],
            config["database"]["db_name"])

        self.queue = Queue.Queue()
        self.process_thread = threading.Thread(target=self.process)
        self.halt_event = threading.Event()

        self.room = config['sensor_location']
        self.measurement = config['database']['measurement_name']

    def get_timestamp(self):
        return datetime.datetime.utcnow().isoformat()

    def process(self):

        while not self.halt_event.isSet():
            try:
                reading = self.queue.get(timeout=5)

            except Queue.Empty:
                pass

            try:
                json_body = [
                    {
                        "measurement": self.measurement,
                        "tags": {
                            "host": socket.gethostname(),
                            "zone": self.room
                        },
                        "time": self.get_timestamp(),
                        "fields": reading
                    }
                ]

                logger.debug(json_body)


                result = self.client.write_points(json_body)
                logger.debug("Influxdb publish result %s", result)

            except Exception, ex:
                logger.exception("Failed during influx report")

    def prepare(self):
        self.process_thread.start()

    def stop(self):
        self.halt_event.set()
        self.process_thread.join()
