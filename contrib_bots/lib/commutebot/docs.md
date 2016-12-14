This bot will allow briefings of estimated travel times,
distances and fare information for transit travel.

It can respond to:
  departure times
  arrival times
  user preferences (toll avoidance, highway avoidance)
  mode of transport

It can output:
  fare information
  more detailed addresses on origin and destiantion
  duration in traffic information
  metric and imperical units
  information in various languages

The bot will respond to the same stream input was in. And if private message, the
bot will reply with a private message.

Sample input and output:

    @commute help

    Obligatory Inputs:
        Origin (origin=New York,NY,USA)
        Destination (destinations=Chicago,IL,USA)
        Mode Of Transport (Accepted inputs:driving, walking, bicycling, transit) (mode=driving)
    Optional Inputs:
        Units (Metric or imperial) (units=metric)
        Restrictions (Accepted inputs:tolls, highways, ferries, indoor) (avoid=tolls)
        Departure Time (Seconds After Midnight January 1, 1970 UTC) (departure_time=now)
        Arrival Time (Seconds After Midnight January 1, 1970 UTC) (arrival_time=732283981023)
        Language (Available languages available here: https://developers.google.com/maps/faq#languagesupport) (lan=fr)

    Sample request:
        @commute origin=Chicago,IL,USA destination=New+York,NY,USA mode=driving language=fr

    Please note:
        Fare information can be derived, though is solely dependent on the availability of the information released by public transport operators
        Duration in traffic can only be derived if a departure time is set.
        If a location has spaces in its name, please use a + symbol in the place of the space/s
        A departure time and a arrival time can not be inputted at the same time
