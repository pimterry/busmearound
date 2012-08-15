from mock import patch, Mock
import json, time

class BusStreamMock(object):

  def __init__(self):
    self.requests_patch = patch('sherpa.buses.requests')
    self.requests = self.requests_patch.__enter__()
    self.requests.get = self._stubbed_get
    self.clear()

  def _stubbed_get(self, url, params = None, auth = None):
    response = Mock()
    response.status_code = 200
    response.text = "\n".join(json.dumps(m) for m in self.messages)
    response.iter_lines.return_value = (json.dumps(m) for m in self.messages)

    return response

  def clear(self):
    self.messages = []
    self.add_ura_version_header()

  def add_ura_version_header(self):
    self.send_raw_message(4, "1.0", int(time.time() * 1000))

  def send_raw_message(self, *args):
    self.messages.append(args)

  def predict_bus(self, bus, stop, arrival_time):
    arrival_time = int(arrival_time)
    self.send_raw_message(1,
                          stop.stop_id,
                          bus.name,
                          bus.destination,
                          bus.bus_id,
                          arrival_time,
                          arrival_time + 30)

  def add_stops(self, *stops):
    for stop in stops:
      self.add_stop(stop)

  def add_stop(self, stop):
    self.send_raw_message(0,
                          stop.name,
                          stop.stop_id,
                          "STBR",
                          stop.indicator,
                          stop.location[0],
                          stop.location[1])

  def close(self):
    self.requests_patch.__exit__()
