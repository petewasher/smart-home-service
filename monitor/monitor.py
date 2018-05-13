#! /usr/bin/python

import argparse
import time
import json
import subprocess
from awsiot import AWSIoTUpdater
from influxdb_reporter import InfluxDBReporter

# Configure logging
import logging
logger = logging.getLogger("Monitor.Main")
logger.setLevel(logging.INFO)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

class TemperatureMonitorBase(object):
    def __init__(self, config):
        self.CPU_HEAT_FACTOR = config['heatfactor']

    def get_cpu_temp(self):
        cpu_temp = subprocess.check_output("vcgencmd measure_temp", shell=True)
        return float(cpu_temp.split('=')[1].split("'C")[0])

    def calibrate(self, sensor_temp):

        cpu_temp = self.get_cpu_temp()
        adjusted_temp = sensor_temp - ((cpu_temp - sensor_temp)/self.CPU_HEAT_FACTOR)
        return adjusted_temp

def monitor_bme680():
    pass

class monitor_envirophat(TemperatureMonitorBase):
    def __init__(self, config):
        super(monitor_envirophat, self).__init__(config)

    def get_next_reading(self):
        from envirophat import weather
        return {
            "temperature": self.calibrate(weather.temperature()),
            "pressure": weather.pressure(unit='hPa')
        }

def monitor_owl():
    pass

class monitor_dummy():
    def __init__(self, config):
        pass

    def get_next_reading(self):
        return {
            "temperature": 24.3,
            "pressure": 1004.001
        }

def main():
    parser = argparse.ArgumentParser(description='Report from hardware')
    parser = argparse.ArgumentParser()
    parser.add_argument('--hardware', help='foo help')
    parser.add_argument('--config', default="config.json")
    args = parser.parse_args()

    logger.debug(args)

    config = {}
    with open(args.config) as config_f:
        data = config_f.read()
        config = json.loads(data)

    reporters = (
        InfluxDBReporter(config),
        AWSIoTUpdater(config),
        )

    hardware_class = {
        #"bme680": monitor_bme680,
        "envirophat": monitor_envirophat,
        #"owl": monitor_owl,
        "dummy": monitor_dummy
    }

    if not args.hardware:
        logger.error("Please specify hardware type from: %s", hardware_class.keys())
        exit()

    hardware = hardware_class[args.hardware](config)

    for reporter in reporters:
        reporter.prepare()

    while True:
        try:
            reading = hardware.get_next_reading()
            for reporter in reporters:
                logger.debug("Put %s %s", reporter, reading)
                reporter.queue.put(reading)

            time.sleep(10)

        except KeyboardInterrupt:
            for reporter in reporters:
                reporter.stop()
            break

if __name__ == "__main__":
    main()