#! /usr/bin/python
import sys
import datetime
import json
from influxdb import InfluxDBClient

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

while 1:
    line = sys.stdin.readline()
    try:
        if line is not '':
           print line
           watts = float(line)
           
           json_body = [
                   {
                       "measurement": "power",
                       "tags": {
                           "host": "power-monitor-1",
                           "zone": "0"
                           },
                       "time": get_timestamp(),
                       "fields": {
                           "watts": watts,
                           }
                       }
                   ]

           print client.write_points(json_body)
    except:
       pass
