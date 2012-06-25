from geopy import distance
from collections import defaultdict
import requests, json, os, time, bisect

distance.distance = distance.GreatCircleDistance

INSTANT_BUS_FEED = 'http://countdown.api.tfl.gov.uk/interfaces/ura/instant_V1'
RELEVANT_BUS_STOP_TYPES = ['STBR', 'STBC', 'STZZ', 'STBS', 'STSS']

class BusStop(object):
  __slots__ = 'stop_id', 'name', 'indicator', 'location'

  def __init__(self, stop_id, name, indicator, location):
    self.stop_id = stop_id
    self.name = name
    self.indicator = indicator
    self.location = location

  def distanceTo(location):
    return distance.distance(self.location, location).meters

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

class Bus(object):
  __slots__ = 'bus_id', 'name', 'destination'

  def __init__(self, bus_id, name, destination):
    self.bus_id = bus_id
    self.name = name
    self.destination = destination

class BusStops(object):
  grid_width = grid_height = 10.0
  min_lat = 51.2
  max_lat = 51.8
  min_long = -0.6
  max_long = 0.35
  cell_width = (max_lat - min_lat) / grid_width
  cell_height = (max_long - min_long) / grid_height

  def __init__(self):
    self.stop_grid = defaultdict(lambda : defaultdict(list))
    self.stops = {}

  def _refresh(self):
    fields = ['StopID',
              'StopPointName',
              'StopPointType',
              'StopPointIndicator',
              'Latitude',
              'Longitude']
    params = { 'ReturnList' : ','.join(fields),
               'StopAlso' : 'True' }

    r = requests.get(INSTANT_BUS_FEED, params = params)

    if r.status_code != 200:
      raise Exception("Could not load bus data: %s" % r.text)

    stops_data = [json.loads(line) for line in r.text.split('\n')]
    URA_header = stops_data.pop(0)

    self.stop_grid = defaultdict(lambda : defaultdict(list))
    self.stops = {}

    for msg_type, name, stop_id, stop_type, indicator, lat, long in stops_data:
      if stop_type not in RELEVANT_BUS_STOP_TYPES:
        continue

      location = (lat, long)
      stop = BusStop(stop_id, name, indicator, location)

      self.stops[stop_id] = stop
      self.get_cell(location).append(stop)


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
    >>> b._get_stops_near((51.1, -0.1), 50)
    [1, 2, 4]
    """
    relevant_stops = []

    for x in self.stop_grid:
      for y in self.stop_grid[x]:
        lat = x * self.cell_width + self.min_lat
        long = y * self.cell_height + self.min_long

        corners = ((lat, long),
                   (lat + self.cell_width, long),
                   (lat, long + self.cell_height),
                   (lat + self.cell_width, long + self.cell_height))
        corner_radius = distance.distance(corners[0], corners[3]).meters/2

        for corner in corners:
          if distance.distance(corner, location).meters <= max(corner_radius, distance_in_meters):
            relevant_stops += self.stop_grid[x][y]
            break

    return relevant_stops

  def near(self, location, distance_in_meters=500):
    return LocalBusStops(self._get_stops_near(location, distance_in_meters), location, distance_in_meters)

  def getBuses(self):
    pass

  def __getitem__(self, key):
    return self.stops[key]

  def __iter__(self):
    return self.stops.__iter__()

  def __len__(self):
    return len(self.stops)

class LocalBusStops(object):

  def __init__(self, all_stops, location, max_distance_in_meters):
    start = time.time()
    self.location = location
    self.stops = []

    for stop in all_stops:
      stop_distance = distance.distance(location, stop.location).meters
      if stop_distance <= max_distance_in_meters:
        bisect.insort(self.stops, DistancedBusStop(stop, stop_distance))

  def __iter__(self):
    pass


class Buses(object):
  def near(self, location):
    pass


if __name__ == "__main__":
  bus_stops = BusStops()
