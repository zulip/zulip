# Analytics

Zulip has a cool analytics system for tracking various useful statistics
that currently power the `/stats` page, and over time will power other
features, like showing usage statistics for the various streams. It is
designed around the following goals:

- Minimal impact on scalability and service complexity.
- Well-tested so that we can count on the results being correct.
- Efficient to query so that we can display data in-app (e.g. on the streams
  page) with minimum impact on the overall performance of those pages.
- Storage size smaller than the size of the main Message/UserMessage
  database tables, so that we can store the data in the main postgres
  database rather than using a specialized database platform.

There are a few important things you need to understand in order to
effectively modify the system.

## Analytics backend overview

There are three main components:

- models: The UserCount, StreamCount, RealmCount, and InstallationCount
  tables (analytics/models.py) collect and store time series data.
- stat definitions: The CountStat objects in the COUNT_STATS dictionary
  (analytics/lib/counts.py) define the set of stats Zulip collects.
- accounting: The FillState table (analytics/models.py) keeps track of what
  has been collected for which CountStats.

The next several sections will dive into the details of these components.

## The *Count database tables

The Zulip analytics system is built around collecting time series data in a
set of database tables. Each of these tables has the following fields:

- property: A human readable string uniquely identifying a CountStat
  object. Example: "active_users:is_bot:hour" or "messages_sent:client:day".
- subgroup: Almost all CountStats are further sliced by subgroup. For
  "active_users:is_bot:day", this column will be False for measurements of
  humans, and True for measurements of bots. For "messages_sent:client:day",
  this column is the client_id of the client under consideration.
- end_time: A datetime indicating the end of a time interval. It will be on
  an hour (or UTC day) boundary for stats collected at hourly (or daily)
  frequency. The time interval is determined by the CountStat.
- various "id" fields: Foreign keys into Realm, UserProfile, Stream, or
  nothing. E.g. the RealmCount table has a foreign key into Realm.
- value: The integer counts. For "active_users:is_bot:hour" in the
  RealmCount table, this is the number of active humans or bots (depending
  on subgroup) in a particular realm at a particular end_time. For
  "messages_sent:client:day" in the UserCount table, this is the number of
  messages sent by a particular user, from a particular client, on the day
  ending at end_time.
- anomaly: Currently unused, but a key into the Anomaly table allowing
  someone to indicate a data irregularity.

There are four tables: UserCount, StreamCount, RealmCount, and
InstallationCount. Every CountStat is initially collected into UserCount,
StreamCount, or RealmCount. Every stat in UserCount and StreamCount is
aggregated into RealmCount, and then all stats are aggregated from
RealmCount into InstallationCount. So for example,
"messages_sent:client:day" has rows in UserCount corresponding to (user,
end_time, client) triples. These are summed to rows in RealmCount
corresponding to triples of (realm, end_time, client). And then these are
summed to rows in InstallationCount with totals for pairs of (end_time,
client).

Note: In most cases, we do not store rows with value 0. See
[Performance Strategy](#performance-strategy) below.

## CountStats

CountStats declare what analytics data should be generated and stored. The
CountStat class definition and instances live in `analytics/lib/counts.py`.
These declarations specify at a high level which tables should be populated
by the system and with what data.

## The FillState table

The default Zulip production configuration runs a cron job once an hour that
updates the *Count tables for each of the CountStats in the COUNT_STATS
dictionary. The FillState table simply keeps track of the last end_time that
we successfully updated each stat. It also enables the analytics system to
recover from errors (by retrying) and to monitor that the cron job is
running and running to completion.

## Performance strategy

An important consideration with any analytics system is performance, since
it's easy to end up processing a huge amount of data inefficiently and
needing a system like Hadoop to manage it. For the built-in analytics in
Zulip, we've designed something lightweight and fast that can be available
on any Zulip server without any extra dependencies through the carefully
designed set of tables in Postgres.

This requires some care to avoid making the analytics tables larger than the
rest of the Zulip database or adding a ton of computational load, but with
careful design, we can make the analytics system very low cost to operate.
Also, note that a Zulip application database has 2 huge tables: Message and
UserMessage, and everything else is small and thus not performance or
space-sensitive, so it's important to optimize how many expensive queries we
do against those 2 tables.

There are a few important principles that we use to make the system
efficient:

- Not repeating work to keep things up to date (via FillState)
- Storing data in the *Count tables to avoid our endpoints hitting the core
  Message/UserMessage tables is key, because some queries could take minutes
  to calculate. This allows any expensive operations to run offline, and
  then the endpoints to server data to users can be fast.
- Doing expensive operations inside the database, rather than fetching data
  to Python and then sending it back to the database (which can be far
  slower if there's a lot of data involved).  The Django ORM currently
  doesn't support the "insert into .. select" type SQL query that's needed
  for this, which is why we use raw database queries (which we usually avoid
  in Zulip) rather than the ORM.
- Aggregating where possible to avoid unnecessary queries against the
  Message and UserMessage tables.  E.g. rather than querying the Message
  table both to generate sent message counts for each realm and again for
  each user, we just query for each user, and then add up the numbers for
  the users to get the totals for the realm.
- Not storing rows when the value is 0. An hourly user stat would otherwise
  collect 24 * 365 * roughly .5MB per db row = 4GB of data per user per
  year, most of whose values are 0. A related note is to be cautious about
  adding queries that are typically non-0 instead of being typically 0.

## Backend Testing

There are a few types of automated tests that are important for this sort of
system:

- Most important: Tests for the code path that actually populates data into
  the analytics tables.  These are most important, because it can be very
  expensive to fix bugs in the logic that generates these tables (one
  basically needs to regenerate all of history for those tables), and these
  bugs are hard to discover.  It's worth taking the time to think about
  interesting corner cases and add them to the test suite.
- Tests for the backend views code logic for extracting data from the
  database and serving it to clients.

For manual backend testing, it sometimes can be valuable to use `./manage.py
dbshell` to inspect the tables manually to check that things look right; but
usually anything you feel the need to check manually, you should add some
sort of assertion for to the backend analytics tests, to make sure it stays
that way as we refactor.

## LoggingCountStats

The system discussed above is designed primarily around the technical
problem of showing useful analytics about things where the raw data is
already stored in the database (e.g. Message, UserMessage).  This is great
because we can always backfill that data to the beginning of time, but of
course sometimes one wants to do analytics on things that aren't worth
storing every data point for (e.g. activity data, request performance
statistics, etc.). There is currently a reference implementation of a
"LoggingCountStat" that shows how to handle such a situation.

## Analytics UI development and testing

### Setup and Testing

The main testing approach for the /stats page UI is manual testing.  For UI
testing, you want a comprehensive initial data set.  You can create
one by using the `./manage.py populate_analytics_db` command from the
main `zulip` directory inside your development environment.

Then, in the development server web UI, (logout if needed) and then
login as the "shylock@analytics.ds" user; note that user's Zulip UI
will be a bit broken, since it doesn't have other data populated
properly.  Finally, go to /stats to see the graphs with the
prepopulated data.

### Adding or editing /stats graphs

The relevant files are:

- analytics/views.py: All chart data requests from the /stats page call
  get_chart_data in this file. The bottom half of this file (with all the
  raw sql queries) is for a different page (/activity), not related to
  /stats.
- static/js/stats/stats.js: The JavaScript and Plotly code.
- templates/analytics/stats.html
- static/styles/stats.css and static/styles/portico.css: We are in the
  process of re-styling this page to use in-app css instead of portico css,
  but there is currently still a lot of portico influence.
- analytics/urls.py: Has the URL routes; it's unlikely you will have to
  modify this, including for adding a new graph.

Most of the code is self-explanatory, and for adding say a new graph, the
answer to most questions is to copy what the other graphs do. It is easy
when writing this sort of code to have a lot of semi-repeated code blocks
(especially in stats.js); it's good to do what you can to reduce this.

Tips and tricks:

- Use `$.get` to fetch data from the backend. You can grep through stats.js
  to find examples of this.
- The Plotly documentation is at
  <https://plot.ly/javascript/> (check out the full reference, event
  reference, and function reference). The documentation pages seem to work
  better in Chrome than in Firefox, though this hasn't been extensively
  verified.
- Unless a graph has a ton of data, it is typically better to just redraw it
  when something changes (e.g. in the various aggregation click handlers)
  rather than to use retrace or relayout or do other complicated
  things. Performance on the /stats page is nice but not critical, and we've
  run into a lot of small bugs when trying to use Plotly's retrace/relayout.
- There is a way to access raw d3 functionality through Plotly, though it
  isn't documented well.
- 'paper' as a Plotly option refers to the bounding box of the graph (or
  something related to that).
- You can't right click and inspect the elements of a Plotly graph (e.g. the
  bars in a bar graph) in your browser, since there is an interaction layer
  on top of it. But if you hunt around the document tree you should be able
  to find it.

### /activity page

- There's a somewhat less developed /activity page, for server
  administrators, showing data on all the realms on a server.  To
  access it, you need to have the `is_staff` bit set on your
  UserProfile object.  You can set it using `manage.py shell` and
  editing the UserProfile object directly.  A great future project is
  to clean up that page's data sources, and make this a documented
  interface.
