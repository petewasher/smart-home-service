import subprocess
import datetime
import time
import json
from influxdb import InfluxDBClient

from envirophat import weather

def get_cpu_temp():
    cpu_temp = subprocess.check_output("vcgencmd measure_temp", shell=True)
    return float(cpu_temp.split('=')[1].split("'C")[0])

print get_cpu_temp()

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

UNIT='hPa'
CPU_HEAT_FACTOR=2.0

try:
    while True:

        cpu_temp = get_cpu_temp()
        sensor_temp = weather.temperature
        adjusted_temp = sensor_temp - ((cpu_temp - sensor_temp)/CPU_HEAT_FACTOR)

        print "CPU: ", cpu_temp
        print "Measured: ", sensor_temp
        print "Adjusted: ", adjusted_temp

        json_body = [
            {
                "measurement": "temperature",
                "tags": {
                    "host": "temperature-monitor-2",
                    "zone": "upstairs"
                },
                "time": get_timestamp(),
                "fields": {
                    "temperature": adjusted_temp,
                    "pressure": weather.pressure(unit=UNIT)
                }
            }
        ]

        print client.write_points(json_body)

        print json_body

        time.sleep(10)

except KeyboardInterrupt:
    pass
