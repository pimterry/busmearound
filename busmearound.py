from flask import Flask, render_template
from datetime import datetime
import json, requests

app = Flask(__name__)

@app.route('/')
def index():
  # TODO: Do this properly silly (problems with js templating in the the template otherwise)
  return open('templates/index.html', 'r').read()

@app.route('/buses-near/<lat>/<long>')
def buses_near(lat, long, range_in_meters=500):
  """
  Takes a latitude and a longitude and tells you when and where the next buses are arriving
  in the surrounding 100 meters.
  """
  interesting_fields = ['StopPointName',
                        'LineName',
                        'Towards',
                        'EstimatedTime',
                        'Latitude',
                        'Longitude']

  params = { 'Circle' : '%s,%s,%s' % (lat, long, range_in_meters),
             'ReturnList' : ','.join(interesting_fields) }

  r = requests.get('http://countdown.api.tfl.gov.uk/interfaces/ura/instant_V1',
                   params = params)
  data = [json.loads(line) for line in r.text.split('\n')]
  bus_data = [line for line in data if line[0] == 1]

  buses = []
  stops = {}

  for msg_type, stop, towards, stop_lat, stop_long, bus, time in bus_data:
    if msg_type != 1:
      continue

    # TODO: Instead, store once for each bus (get bus ids), only return closest
    # stop that bus is going through

    buses.append({ 'name' : bus,
                   'destination' : towards,
                   'unixtime' : time,
                   'stop' : stop })

    stops[stop] = (stop_lat, stop_long)

  return json.dumps({ 'buses' : sorted(buses, key = lambda b : b['unixtime']),
                      'stops' : stops})

if __name__ == "__main__":
  app.debug = True
  app.run()
