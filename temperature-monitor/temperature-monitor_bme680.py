import subprocess
import bme680
import datetime
import time
import json
from influxdb import InfluxDBClient
from awsiot import AWSIoTUpdater

sensor = bme680.BME680()

# Setup from https://github.com/pimoroni/bme680/blob/master/examples/read-all.py
sensor.set_humidity_oversample(bme680.OS_2X)
sensor.set_pressure_oversample(bme680.OS_4X)
sensor.set_temperature_oversample(bme680.OS_8X)
sensor.set_filter(bme680.FILTER_SIZE_3)
sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)

def get_cpu_temp():
    cpu_temp = subprocess.check_output("vcgencmd measure_temp", shell=True)
    return float(cpu_temp.split('=')[1].split("'C")[0])

print get_cpu_temp()

print("\n\nInitial reading:")
for name in dir(sensor.data):
    value = getattr(sensor.data, name)

    if not name.startswith('_'):
        print("{}: {}".format(name, value))

sensor.set_gas_heater_temperature(320)
sensor.set_gas_heater_duration(150)
sensor.select_gas_heater_profile(0)

config = {}
with open("./config.json") as config_f:
    data = config_f.read()
    config = json.loads(data)

client = InfluxDBClient(
    config["database"]["host"],
    config["database"]["port"],
    config["database"]["username"],
    config["database"]["password"],
    config["database"]["db_name"])

def get_timestamp():
    return datetime.datetime.utcnow().isoformat()

CPU_HEAT_FACTOR=config['heatfactor']

aws_iot = AWSIoTUpdater(config)


try:
    while True:
        if sensor.get_sensor_data():

            cpu_temp = get_cpu_temp()
            sensor_temp = sensor.data.temperature
            adjusted_temp = sensor_temp - ((cpu_temp - sensor_temp)/CPU_HEAT_FACTOR)

            print "CPU: ", cpu_temp
            print "Measured: ", sensor_temp
            print "Adjusted: ", adjusted_temp

            json_body = [
                {
                    "measurement": "temperature",
                    "tags": {
                        "host": "temperature-monitor-1",
                        "zone": "downstairs"
                    },
                    "time": get_timestamp(),
                    "fields": {
                        "temperature": adjusted_temp,
                        "humidity": sensor.data.humidity,
                        "pressure": sensor.data.pressure,
                        "gas_resistance": None if not sensor.data.heat_stable else sensor.data.gas_resistance
                    }
                }
            ]

            aws_iot.connect()
            aws_iot.publish({
                "room": config['sensor_location'],
                "temperature": adjusted_temp
            })
            aws_iot.disconnect()

            print client.write_points(json_body)

            print json_body

        time.sleep(10)

except KeyboardInterrupt:
    pass
