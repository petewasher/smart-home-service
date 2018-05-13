#! /usr/bin/python

import argparse
import time
import json
import subprocess
from awsiot import AWSIoTUpdater

def TemperatureMonitorBase(object):
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
        return 855.223

def main():
    parser = argparse.ArgumentParser(description='Report from hardware')
    parser = argparse.ArgumentParser()
    parser.add_argument('--hardware', help='foo help')
    args = parser.parse_args()

    config = {}
    with open("./config.json") as config_f:
        data = config_f.read()
        config = json.loads(data)

    reporters = (
        #influxdb(),
        AWSIoTUpdater(config),
        )

    hardware_class = {
        #"bme680": monitor_bme680,
        "envirophat": monitor_envirophat,
        #"owl": monitor_owl,
        "dummy": monitor_dummy
    }

    if not args.hardware:
        print "Please specify hardware type from: %s" % hardware_class.keys()
        exit()

    hardware = hardware_class[args.hardware](config)

    for reporter in reporters:
        reporter.prepare()

    while True:
        try:
            reading = hardware.get_next_reading()
            for reporter in reporters:
                reporter.queue.put(reading)

            time.sleep(5)
        except KeyboardInterrupt:
            for reporter in reporters:
                reporter.stop()
            break









if __name__ == "__main__":
    main()