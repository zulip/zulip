This bot will allow briefings of estimated travel times, distances and
fare information for transit travel.

It can respond to: departure times, arrival times, user preferences
(toll avoidance, highway avoidance) and a mode of transport

It can output: fare information, more detailed addresses on origin and
destination, duration in traffic information, metric and imperical
units and information in various languages.

The bot will respond to the same stream input was in. And if called as
private message, the bot will reply with a private message.

To setup the bot, you will first need to move commute.config into
the user home directory and add an API key.

Move

```
~/zulip/contrib_bots/bots/commute/commute.config
```

into

```
~/commute.config
```

To add an API key, please visit:
https://developers.google.com/maps/documentation/distance-matrix/start
to retrieve a key and copy your api key into commute.config

Sample input and output:

<pre><code>@commute help</code></pre>

<pre><code>Obligatory Inputs:
    Origin e.g. origins=New+York,NY,USA
    Destination e.g. destinations=Chicago,IL,USA

Optional Inputs:
    Mode Of Transport (inputs: driving, walking, bicycling, transit)
    Default mode (no mode input) is driving
    e.g. mode=driving or mode=transit
    Units (metric or imperial)
    e.g. units=metric
    Restrictions (inputs: tolls, highways, ferries, indoor)
    e.g. avoid=tolls
    Departure Time (inputs: now or (YYYY, MM, DD, HH, MM, SS) departing)
    e.g. departure_time=now or departure_time=2016,12,17,23,40,40
    Arrival Time (inputs: (YYYY, MM, DD, HH, MM, SS) arriving)
    e.g. arrival_time=2016,12,17,23,40,40
    Languages:
    Languages list: https://developers.google.com/maps/faq#languagesupport)
    e.g. language=fr
</code></pre>

Sample request:
    <pre><code>
    @commute origins=Chicago,IL,USA destinations=New+York,NY,USA language=fr
    </code></pre>

Please note:
    Fare information can be derived, though is solely dependent on the
    availability of the information released by public transport operators.
    Duration in traffic can only be derived if a departure time is set.
    If a location has spaces in its name, please use a + symbol in the
    place of the space/s.
    A departure time and a arrival time can not be inputted at the same time
    No spaces within addresses.
    Departure times and arrival times must be in the UTC timezone,
    you can use the timezone bot.
