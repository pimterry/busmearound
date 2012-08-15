import unittest
from ..buses import *
from .bus_stream_mock import BusStreamMock

class BusStopsTest(unittest.TestCase):

  def setUp(self):
    self.stream = BusStreamMock()

  def tearDown(self):
    self.stream.close()

  def test_should_iterate_correctly_over_all_provided_stops(self):
    stop1 = BusStop(1, "stop", None, (0,0))
    stop2 = BusStop(2, "other stop", "F", (0,0))
    stop3 = BusStop(30, "stop 30", "North", (0,0))

    self.stream.add_stops(stop1, stop2, stop3)
    bus_stops = BusStops()
    bus_stops._refresh_stops()
    stops = bus_stops.stops

    assert len(stops) == 3
    assert stops[stop1.stop_id] == stop1
    assert stops[stop2.stop_id] == stop2
    assert stops[stop3.stop_id] == stop3

  def test_should_read_predictions_from_stream(self):
    stop1 = BusStop(1, "stop", None, (0, 0))
    stop2 = BusStop(2, "stop 2", None, (0, 0))

    self.stream.add_stops(stop1, stop2)
    bus_stops = BusStops()
    bus_stops._refresh_stops()

    bus1 = Bus(10, "Bus", "London")
    bus1_arrival_time = time.time() * 1000
    bus2 = Bus(11, "Bus 2", "London")
    bus2_arrival_time = bus1_arrival_time + 60000

    self.stream.clear()
    self.stream.predict_bus(bus1, stop1, bus1_arrival_time)
    self.stream.predict_bus(bus2, stop1, bus2_arrival_time)
    bus_stops._stream_predictions()

    arrivals = bus_stops.stops[stop1.stop_id].buses

    assert len(arrivals) == 2
    assert bus1 in arrivals
    assert bus2 in arrivals
    assert arrivals[bus1] == bus1_arrival_time
    assert arrivals[bus2] == bus2_arrival_time

  def test_should_ignore_other_message_types(self):
    self.stream.send_raw_message(2, "qwe", "asd")
    self.stream.send_raw_message(3, "123qwe")

    bus_stops = BusStops()

    bus_stops._refresh_stops()
    stops = bus_stops.stops
    assert len(stops) == 0

    bus_stops._stream_predictions()
    stops = bus_stops.stops
    assert len(stops) == 0

  def test_should_return_stops_near_location_only(self):
    search_location = (51.1, -0.1)

    stop1 = BusStop(1, "Stop", None, search_location)
    stop2 = BusStop(2, "Stop", None, (51.5, -0.1))   # 50km away
    stop3 = BusStop(3, "Stop", None, (51.1, -0.11))  # 700m away
    stop4 = BusStop(4, "Stop", None, (51.1, -0.101)) # 70m away
    stop5 = BusStop(5, "Stop", None, (51.099, -0.1)) # 111m away
    stop6 = BusStop(6, "Stop", None, (51.098, -0.1)) # 222m away
    self.stream.add_stops(stop1, stop2, stop3, stop4, stop5)

    bus_stops = BusStops()
    bus_stops._refresh_stops()
    # Get all stops within 200m 
    nearby_stops = bus_stops.near(search_location, 200).sorted_stops

    assert [stop.stop_id for stop in nearby_stops] == [1, 4, 5]
