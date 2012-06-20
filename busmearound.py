from flask import Flask, render_template
from datetime import datetime
import json, requests, os, time
from geopy import distance

app = Flask(__name__)

@app.route('/')
def index():
  # TODO: Do this properly silly (problems with js templating in the the template otherwise)
  return open('templates/index.html', 'r').read()

@app.route('/buses-near/<lat>/<long>')
def bus_data_near(lat, long, range_in_meters=300):
  """
  Takes a latitude and a longitude and tells you when and where the next buses are arriving
  in the surrounding 100 meters.
  """
  interesting_fields = ['StopPointName',
                        'StopID',
                        'StopPointIndicator',
                        'Latitude',
                        'Longitude',
                        'LineName',
                        'DestinationText',
                        'VehicleID',
                        'EstimatedTime']

  params = { 'Circle' : '%s,%s,%s' % (lat, long, range_in_meters),
             'ReturnList' : ','.join(interesting_fields) }

  r = requests.get('http://countdown.api.tfl.gov.uk/interfaces/ura/instant_V1',
                   params = params)

  data = [json.loads(line) for line in r.text.split('\n')]
  bus_data = [line for line in data if line[0] == 1]

  buses = {}
  stops = {}

  now = time.time() - 60

  for msg_type, stop_name, stop_id, stop_indicator, stop_lat, stop_long, bus_name, destination, bus_id, time_millis in bus_data:
    distance = distance_between((lat, long), (stop_lat, stop_long))

    if stop_id not in stops:
      if stop_indicator:
        stop_name = "%s (Stop %s)" % (stop_name, stop_indicator)
      stops[stop_id] = { 'name' : stop_name,
                         'lat' : stop_lat,
                         'long' : stop_long,
                         'distance' : distance }

    # Skip any stops you probably couldn't get to in time
    if (time_millis/1000 - distance/2) < now:
      continue

    if bus_id not in buses or distance < stops[buses[bus_id]['stop_id']]['distance']:
      buses[bus_id] = { 'name' : bus_name,
                       'destination' : destination,
                       'time_millis' : time_millis,
                       'stop_id' : stop_id,
                       'distance_to_stop' : distance }

  return json.dumps({ 'buses' : sorted(buses.values(), key = lambda b : b['time_millis']),
                      'stops' : stops})

def distance_between(start, end):
  return distance.distance(start, end).meters

if __name__ == "__main__":
  app.debug = True
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port)
