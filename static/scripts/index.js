page = new function() {
  this.openPanelListener = function() {
    self = this;
    return function() {
      bus_data = $(this).data('bus');
      bus_panel = ich.bus_panel(bus_data);
      bus_panel.data('bus', bus_data);
      bus_panel.click(self.closePanelListener());

      // Need to stop us closing the panel when we hit the show map link
      // (so if you go back to the browser in android, the panel's still open)
      bus_panel.find('a').click(function(e) {
        e.stopPropagation();
      })

      $(this).replaceWith(bus_panel);
    }
  }

  this.closePanelListener = function() {
    self = this;
    return function() {
      bus_data = $(this).data('bus');
      bus_arrival = ich.bus_arrival(bus_data);
      bus_arrival.data('bus', bus_data);
      bus_arrival.click(self.openPanelListener());

      $(this).replaceWith(bus_arrival);
    }
  }

  this.setStatusMessage = function(msg) {
    $('#loading').html(msg);
    $('#loading').show();
  }

  this.clearStatusMessage = function() {
    $('#loading').hide();
    $('#loading').html('');
  }

  this.addBusArrival = function(index, bus) {
    arrival_time = moment(bus.time_millis);
    bus.time = arrival_time.format('h:mma');
    bus.eta = arrival_time.fromNow();
    stop = stops[bus.stop_id]
    bus.stop = stop.name;
    bus.lat = stop.lat
    bus.long = stop.long
    bus.distance_to_stop = Math.round(bus.distance_to_stop);

    bus_html = ich.bus_arrival(bus);
    if (index % 3 == 0) bus_html.css('clear', 'both');
    bus_html.data('bus', bus);
    bus_html.click(this.openPanelListener());

    $("#buses").append(bus_html);
  }

  this.error = function() {
    setStatusMessage("Sorry, an error occurred.");
  }
}

TravelDataSource = function() {

  this.DATA_EXPIRY_MILLIS = 30000;

  this.waitingForData = false;
  this.lastPosition;

  this.init = function() {
    moment.relativeTime.m = "1 minute";
    this.waitingForData = false;
    this.lastPosition = null;
  }

  this.loadBusData = function() {
    // Show loading messages when during ajax loads
    $.ajaxSetup({
      beforeSend: function() {
        page.setStatusMessage("Loading data...");
      },
      complete: page.clearStatusMessage,
      success: function() {}
    });

    if (navigator.geolocation) {
      page.setStatusMessage("Finding your location...");
      positionListener = $.proxy(this.positionFound, this);
      navigator.geolocation.watchPosition(positionListener, page.error,
                                          { enableHighAccuracy: true });
    } else {
      page.setStatusMessage("Sorry, geolocation isn't supported on your device");
    }
  }

  this.positionFound = function(position) {
    if (!this.isPositionDataUseful(position)) return;

    lat = position.coords.latitude;
    long = position.coords.longitude;

    this.waitingForData = true;
    $.getJSON("/buses-near/" + lat + "/" + long, this.busArrivalsListener(position))
  }

  this.isPositionDataUseful = function(position) {
    if (this.waitingForData) return false;

    if (this.lastPosition == null) {
      return true;
    }

    if (position.timestamp - this.lastPosition.timestamp > this.DATA_EXPIRY_MILLIS) {
      return true;
    }

    if (position.coords.accuracy < this.lastPosition.coords.accuracy * 3/4) {
      return true;
    }

    return false;
  }

  this.busArrivalsListener = function(position) {
    return $.proxy(function(arrivals) {
      page.clearStatusMessage();
      this.lastPosition = position;

      buses = arrivals['buses'];
      stops = arrivals['stops'];
      $("#buses").empty();

      $.each(buses, $.proxy(page.addBusArrival, page));
      this.waitingForData = false;
    }, this);
  }

}
travelDataSource = new TravelDataSource();
