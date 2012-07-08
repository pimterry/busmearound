from geopy import distance
from collections import defaultdict
import requests, json, os, time, bisect, math
from requests.auth import HTTPDigestAuth

distance.distance = distance.GreatCircleDistance

INSTANT_BUS_FEED = 'http://countdown.api.tfl.gov.uk/interfaces/ura/instant_V1'

STREAM_BUS_FEED = 'http://countdown.api.tfl.gov.uk/interfaces/ura/stream_V1'
STREAM_USERNAME = os.getenv('tfl-bus-stream-username')
STREAM_PASSWORD = os.getenv('tfl-bus-stream-password')

RELEVANT_BUS_STOP_TYPES = ['STBR', 'STBC', 'STZZ', 'STBS', 'STSS']

class BusStop(object):
  __slots__ = 'stop_id', 'name', 'indicator', 'location', 'buses'

  def __init__(self, stop_id, name, indicator, location):
    self.stop_id = stop_id
    self.name = name
    self.indicator = indicator
    self.location = location
    self.buses = {}

  def distanceTo(location):
    return distance.distance(self.location, location).meters

  def __str__(self):
    if self.indicator:
      return"%s (Stop %s)" % (self.name, self.indicator)
    else:
      return self.name

  def __repr__(self):
    return "%s-(%s)" % (self.stop_id, self.location)

class DistancedBusStop(object):
  """
  Decorator (pattern-sense, not python-sense) for bus stops that adds a distance
  parameter, to record the distance of the stop from a specific point.
  """
  __slots__ = ('bus_stop', 'distance')

  def __init__(self, bus_stop, stop_distance):
    self.distance = stop_distance
    self.bus_stop = bus_stop

  def __getattr__(self, name):
    return getattr(self.bus_stop, name)

  def __cmp__(self, other):
    return cmp(self.distance, other.distance)

  def __str__(self):
    return "%s - %s meters away" % (self.bus_stop, self.distance)

  def __repr__(self):
    return repr("%s-%sm" % (self.bus_stop, self.distance))

class Bus(object):
  __slots__ = 'bus_id', 'name', 'destination'

  def __init__(self, bus_id, name, destination):
    self.bus_id = bus_id
    self.name = name
    self.destination = destination

  def __hash__(self):
    return self.bus_id

  def __str__(self):
    return "%s towards %s" % (self.name, self.destination)

  def __repr__(self):
    return "%s-%s-%s" % (self.bus_id, self.name, self.destination)

class BusStops(object):
  grid_width = grid_height = 50.0
  min_lat = 51.2
  max_lat = 51.8
  min_long = -0.6
  max_long = 0.35
  cell_width = (max_lat - min_lat) / grid_width
  cell_height = (max_long - min_long) / grid_height

  bus_stop_fields = ['StopID',
                     'StopPointName',
                     'StopPointType',
                     'StopPointIndicator',
                     'Latitude',
                     'Longitude']

  bus_prediction_fields = ['StopID',
                           'LineName',
                           'DestinationText',
                           'VehicleID',
                           'EstimatedTime',
                           'ExpireTime']

  def __init__(self):
    self._reset_data()

  def _refresh(self):
    params = { 'ReturnList' : ','.join(self.bus_stop_fields),
               'StopAlso' : 'True' }

    r = requests.get(INSTANT_BUS_FEED, params = params)

    if r.status_code != 200:
      raise Exception("Could not load bus data: %s" % r.text)

    stops_data = [json.loads(line) for line in r.text.split('\n')]
    URA_header = stops_data.pop(0)

    self._reset_data()

    for msg_type, name, stop_id, stop_type, indicator, lat, long in stops_data:
      self._process_stop_data(name, stop_id, stop_type, indicator, lat, long)

  def _stream_predictions(self):
    params = { 'ReturnList' : ','.join(self.bus_prediction_fields) }
    r = requests.get(STREAM_BUS_FEED,
                     params = params,
                     auth = HTTPDigestAuth(STREAM_USERNAME, STREAM_PASSWORD))

    if r.status_code != 200:
      raise Exception("Could not get bus prediction stream: %s" % r.text)

    for line in r.iter_lines():
      if not line:
        continue

      line_data = json.loads(line)

      # Only look at prediction results (ignore version rows, etc)
      if line_data.pop(0) != 1:
        continue

      stop_id, bus_name, destination, bus_id, arrival_time, expiry_time = line_data

      if stop_id not in self.stops:
        continue

      if expiry_time == 0:
        try:
          del self.stops[stop_id].buses[self.buses[bus_id]]
        except KeyError, e:
          pass

      else:
        self._process_prediction_data(stop_id, bus_name, destination, bus_id, arrival_time)

  def _reset_data(self):
    self.stop_grid = defaultdict(lambda : defaultdict(list))
    self.stops = {}
    self.buses = {}

  def _process_stop_data(self, name, stop_id, stop_type, indicator, lat, long):
    if stop_type not in RELEVANT_BUS_STOP_TYPES:
      return

    location = (lat, long)
    stop = BusStop(stop_id, name, indicator, location)

    self.stops[stop_id] = stop
    self.get_cell(location).append(stop)

  def _process_prediction_data(self, stop_id, bus_name, destination, bus_id, time_millis):
    """
    New bus predirection for bus with the given id.
    """
    if stop_id not in self.stops:
      return

    if bus_id not in self.buses:
      self.buses[bus_id] = Bus(bus_id, bus_name, destination)
    else:
      # Make sure the bus metadata is still valid, since it might've changed 
      # (I think, spec is not too clear on this)
      self.buses[bus_id].name = bus_name
      self.buses[bus_id].destination = destination

    stop = self.stops[stop_id]
    stop.buses[self.buses[bus_id]] = time_millis

  def get_cell(self, (lat, long)):
    """
    Gets the relevant grid cell for a given latitude and longitude.

    >>> b = BusStops()
    >>> b.get_cell((51.5, -0.1))
    []
    >>> b.get_cell((51.5, -0.1)).append(2)
    >>> b.get_cell((51.5, -0.1))
    [2]
    >>> b.get_cell((51.5, -0.2))
    []
    >>> b.get_cell((51.6, -0.1))
    []
    """
    cell_lat = (lat - self.min_lat) // self.cell_width
    cell_long = (long - self.min_long) // self.cell_height
    return self.stop_grid[cell_lat][cell_long]

  def _get_stops_near(self, location, distance_in_meters):
    """
    >>> b = BusStops()
    >>> b.get_cell((51.1, -0.1)).append(1)
    >>> b.get_cell((51.1, -0.1)).append(2)
    >>> b.get_cell((51.5, -0.1)).append(3)
    >>> b.get_cell((51.1, -0.11)).append(4)
    >>> b.get_cell((51.1, -0.101)).append(5)
    >>> b._get_stops_near((51.1, -0.1), 50)
    [1, 2, 5]
    """
    relevant_stops = []

    for x in self.stop_grid:
      for y in self.stop_grid[x]:
        lat = x * self.cell_width + self.min_lat
        long = y * self.cell_height + self.min_long

        cell_centre = (lat + self.cell_width/2, long + self.cell_height/2)
        cell_radius = distance.distance((cell_centre), (lat, long)).meters

        if distance.distance(cell_centre, location).meters <= cell_radius + distance_in_meters:
          relevant_stops += self.stop_grid[x][y]

    return relevant_stops

  def near(self, location, distance_in_meters=500):
    return LocalBusStops(self._get_stops_near(location, distance_in_meters), location, distance_in_meters)

  def getBuses(self):
    pass

  def __getitem__(self, key):
    return self.stops[key]

  def __iter__(self):
    return self.stops.values().__iter__()

  def __len__(self):
    return len(self.stops)

class LocalBusStops(object):

  def __init__(self, all_stops, location, max_distance_in_meters):
    """
    Sets up a collection of local bus stops: filtering all_stops and including
    every stop within max_distance of location indexed by id in .stops, and
    provided in sorted order in .sorted_stops.
    """
    self.location = location
    self.stops = {}
    self.sorted_stops = []

    for stop in all_stops:
      stop_distance = distance.distance(location, stop.location).meters
      if stop_distance <= max_distance_in_meters:
        bisect.insort(self.sorted_stops, DistancedBusStop(stop, stop_distance))
        self.stops[stop.stop_id] = stop

  def __iter__(self):
    return self.sorted_stops.__iter__()

  def __len__(self):
    return len(self.sorted_stops)


class Buses(object):
  def near(self, location):
    pass


if __name__ == "__main__":
  import doctest
  doctest.testmod(verbose=True)
