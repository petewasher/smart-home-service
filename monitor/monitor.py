#! /usr/bin/python

import argparse
import time
import json
import subprocess
import threading
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

    def prepare(self):
        pass

    def cleanup(self):
        pass

    def calibrate(self, sensor_temp):

        cpu_temp = self.get_cpu_temp()
        adjusted_temp = sensor_temp - ((cpu_temp - sensor_temp)/self.CPU_HEAT_FACTOR)
        return adjusted_temp

class monitor_envirophat(TemperatureMonitorBase):
    def __init__(self, config):
        super(monitor_envirophat, self).__init__(config)
        from envirophat import weather
        self.sensor = weather

    def prepare(self):
        pass

    def cleanup(self):
        pass

    def get_next_reading(self):
        return {
            "temperature": self.calibrate(self.sensor.temperature()),
            "pressure": self.sensor.pressure(unit='hPa')
        }

class monitor_bme680(TemperatureMonitorBase):
    def __init__(self, config):
        super(monitor_bme680, self).__init__(config)
        import bme680
        self.sensor = bme680.BME680()
        self.sensor.set_humidity_oversample(bme680.OS_2X)
        self.sensor.set_pressure_oversample(bme680.OS_4X)
        self.sensor.set_temperature_oversample(bme680.OS_8X)
        self.sensor.set_filter(bme680.FILTER_SIZE_3)
        self.sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)

        self.sensor.set_gas_heater_temperature(320)
        self.sensor.set_gas_heater_duration(150)
        self.sensor.select_gas_heater_profile(0)

        self.iaq_calc_thread = threading.Thread(target=self.measure)
        self.halt_event = threading.Event()

        self.iaq = None
        self.humidity = 0
        self.pressure = 0
        self.temperature = 0

        self.burn_in_data = []

        self.sensor_ready = False

    def measure(self):
        while not self.halt_event.isSet():
            try:
                if self.sensor.get_sensor_data() and self.sensor.data.heat_stable:
                    gas = self.sensor.data.gas_resistance
                    gas_offset = gas_baseline - gas

                    hum = self.sensor.data.humidity
                    hum_offset = hum - hum_baseline

                    # Calculate hum_score as the distance from the hum_baseline.
                    if hum_offset > 0:
                        hum_score = (100 - hum_baseline - hum_offset) / (100 - hum_baseline) * (hum_weighting * 100)

                    else:
                        hum_score = (hum_baseline + hum_offset) / hum_baseline * (hum_weighting * 100)

                    # Calculate gas_score as the distance from the gas_baseline.
                    if gas_offset > 0:
                        gas_score = (gas / gas_baseline) * (100 - (hum_weighting * 100))

                    else:
                        gas_score = 100 - (hum_weighting * 100)

                    # Calculate air_quality_score.
                    air_quality_score = hum_score + gas_score

                    self.iaq = air_quality_score
                    self.humidity = self.sensor.data.humidity
                    self.temperature = self.sensor.data.temperature
                    self.pressure = self.sensor.data.pressure

            except Exception, ex:
                logger.exception("Error getting sensor data")

    def prepare(self):
        burn_in_time = 300
        logger.info("Performing burn in. This will take %ss.", burn_in_time)

        start_time = time.time()
        curr_time = time.time()

        self.burn_in_data = []

        while curr_time - start_time < burn_in_time:
            curr_time = time.time()
            if self.sensor.get_sensor_data() and self.sensor.data.heat_stable:
                gas = self.sensor.data.gas_resistance
                burn_in_data.append(gas)
                logger.debug("Gas: {0} Ohms".format(gas))
                time.sleep(1)

        logger.info("Burn in complete.")

        gas_baseline = sum(self.burn_in_data[-50:]) / 50.0

        # Set the humidity baseline to 40%, an optimal indoor humidity.
        hum_baseline = 40.0

        # This sets the balance between humidity and gas reading in the
        # calculation of air_quality_score (25:75, humidity:gas)
        hum_weighting = 0.25

        logger.info("Gas baseline: {0} Ohms, humidity baseline: {1:.2f} %RH\n".format(gas_baseline, hum_baseline))

        self.iaq_calc_thread.start()

    def cleanup(self):
        self.halt_event.set()
        self.iaq_calc_thread.join()

    def get_next_reading(self):
        return {
            "temperature": self.calibrate(self.temperature),
            "pressure": self.pressure,
            "humidity": self.humidity,
            "iaq": self.iaq
        }

def monitor_owl():
    pass

class monitor_dummy():
    def __init__(self, config):
        pass

    def prepare(self):
        pass

    def cleanup(self):
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
    hardware.prepare()

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

            hardware.cleanup()

            break

if __name__ == "__main__":
    main()