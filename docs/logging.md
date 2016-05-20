# Logging and Performance Debugging

It's good to have the terminal running `run-dev.py` up as you work since error
messages including tracebacks along with every backend request will be printed
there.

The messages will look similar to:

```
2016-05-20 14:50:22,056 INFO     127.0.0.1       GET     302 528ms (db: 1ms/1q) (+start: 123ms) / (unauth via ?)
[20/May/2016 14:50:22]"GET / HTTP/1.0" 302 0
2016-05-20 14:50:22,272 INFO     127.0.0.1       GET     200 124ms (db: 3ms/2q) /login/ (unauth via ?)
2016-05-20 14:50:26,333 INFO     127.0.0.1       POST    302  37ms (db: 6ms/7q) /accounts/login/local/ (unauth via ?)
[20/May/2016 14:50:26]"POST /accounts/login/local/ HTTP/1.0" 302 0
2016-05-20 14:50:26,538 INFO     127.0.0.1       GET     200  12ms (db: 1ms/2q) (+start: 53ms) /api/v1/events [1463769771:0/0] (cordelia@zulip.com via internal)
2016-05-20 14:50:26,657 INFO     127.0.0.1       GET     200  10ms (+start: 8ms) /api/v1/events [1463769771:0/0] (cordelia@zulip.com via internal)
2016-05-20 14:50:26,959 INFO     127.0.0.1       GET     200 588ms (db: 26ms/21q) / [1463769771:0] (cordelia@zulip.com via website)
```

The format of this output is: timestamp, loglevel, IP, HTTP Method, HTTP status
code, time to process, (optional perf data details, e.g. database time/queries,
memcached time/queries, Django process startup time, markdown processing time,
etc.), URL, and "email via client" showing user account involved (if logged in)
and the type of client they used ("web", "Android", etc.).
