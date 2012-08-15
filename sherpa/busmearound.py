from flask import Flask, render_template
from datetime import datetime
import json, requests, os, time
from geopy import distance
from buses import BusStops
from threading import Thread

app = Flask(__name__)

@app.route('/')
def index():
  # TODO: Do this properly silly (problems with js templating in the the template otherwise)
  return open('sherpa/templates/index.html', 'r').read()

busStops = BusStops()
busStops._refresh_stops()
Thread(target=busStops._stream_predictions).start()

@app.route('/buses-near/<lat>/<long>')
def bus_data_near(lat, long, range_in_meters=1000):
  """
  Takes a latitude and a longitude and tells you when and where the next buses are arriving
  in the surrounding 1000 meters.
  """
  position = (lat, long)
  now = time.time() - 30 # -30 to add a little slack, so buses right now right next
                         # to you don't get skipped.

  stops = {}
  buses = {}

  relevant_stops = busStops.near(position, range_in_meters)
  for stop in relevant_stops:
    distance = distance_between(position, stop.location)

    if stop.stop_id not in stops:
      stops[stop.stop_id] = { 'name' : stop.name,
                              'lat' : stop.location[0],
                              'long' : stop.location[1],
                              'distance' : distance }

    for bus, arrival_time in stop.buses.items():
      if (arrival_time/1000 - distance / 2) < now:
        continue

      if bus.bus_id not in buses:
        buses[bus.bus_id] = { 'name' : bus.name,
                              'destination' : bus.destination,
                              'time_millis' : arrival_time,
                              'stop_id' : stop.stop_id,
                              'distance_to_stop' : distance }

  return json.dumps({ 'buses' : sorted(buses.values(), key = lambda b : b['time_millis']),
                      'stops' : stops})

def distance_between(start, end):
  return distance.distance(start, end).meters

if __name__ == "__main__":
  app.debug = True
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port)
