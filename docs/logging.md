# Logging and Performance Debugging

It's good to have the terminal running `run-dev.py` up as you work since error
messages including tracebacks along with every backend request will be printed
there.

The format of this output is: timestamp, loglevel, IP, HTTP Method, HTTP status
code, time to process, (optional perf data details, e.g. database time/queries,
memcached time/queries, Django process startup time, markdown processing time,
etc.), URL, and "email via client" showing user account involved (if logged in)
and the type of client they used ("web", "Android", etc.).
