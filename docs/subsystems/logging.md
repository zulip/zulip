# Logging and Error reporting

Having a good system for logging error reporting is essential to
making a large project like Zulip successful.  Without reliable error
reporting, one has to rely solely on bug reports from users in order
to produce a working product.

Our goal as a project is to have zero known 500 errors on the backend
and zero known JavaScript exceptions on the frontend.  While there
will always be new bugs being introduced, that goal is impossible
without an efficient and effective error reporting framework.

We expect to in the future integrate a service like [Sentry][sentry]
to make it easier for very large installations like zulipchat.com to
manage their exceptions and ensure they are all tracked down, but our
default email-based system is great for small installations.

## Backend error reporting

The [Django][django-errors] framework provides much of the
infrastructure needed by our error reporting system:

* The ability to send emails to the server's administrators with any
  500 errors, using the `mail_admins` function.  We enhance these data
  with extra details (like what user was involved in the error) in
  `zerver/logging_handlers.py`, and then send them to the
  administrator in `zerver/lib/error_notify.py` (which also supports
  sending Zulips to a stream about production errors).
* The ability to rate-limit certain errors to avoid sending hundreds
  of emails in an outage (see `_RateLimitFilter` in
  `zerver/lib/logging_util.py`)
* A nice framework for filtering passwords and other important user
  data from the exception details, which we use in
  `zerver/filters.py`.
* Middleware for handling `JsonableError`, our system for allowing
  code anywhere in Django to report an API-facing `json_error` from
  anywhere in a view code path.

Since 500 errors in any Zulip server are usually a problem the server
administrator should investigate and/or report upstream, we have this
email reporting system configured to report errors by default.

### Backend logging

[Django's logging system][django-logging] uses the standard
[Python logging infrastructure][python-logging].  We have configured
them so that `logging.exception` and `logging.error` get emailed to
the server maintainer, while `logging.warning` will just appear in
`/var/log/zulip/errors.log`.  Lower log levels just appear in the main
server log (as well as in the log for corresponding process, be it
`django.log` for the main Django processes or the appropriate
`events_*` log file for a queue worker).

#### Backend logging format

The main Zulip server log contains a line for each backend request.
It also contains warnings, errors, and the full tracebacks for any
Python exceptions.  In production, it goes to
`/var/log/zulip/server.log`; in development, it goes to the terminal
where you run `run-dev.py`.

In development, it's good to keep an eye on the `run-dev.py` console
as you work on backend changes, since it's a great way to notice bugs
you just introduced.

In production, one usually wants to look at `errors.log` for errors
since the main server log can be very verbose, but the main server log
can be extremely valuable for investigating performance problems.

```
2016-05-20 14:50:22.056 INFO [zr] 127.0.0.1       GET     302 528ms (db: 1ms/1q) (+start: 123ms) / (unauth via ?)
[20/May/2016 14:50:22]"GET / HTTP/1.0" 302 0
2016-05-20 14:50:22.272 INFO [zr] 127.0.0.1       GET     200 124ms (db: 3ms/2q) /login/ (unauth via ?)
2016-05-20 14:50:26.333 INFO [zr] 127.0.0.1       POST    302  37ms (db: 6ms/7q) /accounts/login/local/ (unauth via ?)
[20/May/2016 14:50:26]"POST /accounts/login/local/ HTTP/1.0" 302 0
2016-05-20 14:50:26.538 INFO [zr] 127.0.0.1       POST    200  12ms (db: 1ms/2q) (+start: 53ms) /api/v1/events/internal [1463769771:0/0] (cordelia@zulip.com via internal)
2016-05-20 14:50:26.657 INFO [zr] 127.0.0.1       POST    200  10ms (+start: 8ms) /api/v1/events/internal [1463769771:0/0] (cordelia@zulip.com via internal)
2016-05-20 14:50:26.959 INFO [zr] 127.0.0.1       GET     200 588ms (db: 26ms/21q) / [1463769771:0] (cordelia@zulip.com via website)
```

The format of this output is:
* Timestamp
* Log level
* Logger name, abbreviated as "zr" for these Zulip request logs
* IP address
* HTTP method
* HTTP status code
* Time to process
* (Optional perf data details, e.g. database time/queries, memcached
time/queries, Django process startup time, markdown processing time,
etc.)
* Endpoint/URL from zproject/urls.py
* "email via client" showing user account involved (if logged in) and
the type of client they used ("web", "Android", etc.).

The performance data details are particularly useful for investigating
performance problems, since one can see at a glance whether a slow
request was caused by delays in the database, in the markdown
processor, in memcached, or in other Python code.

One useful thing to note, however, is that the database time is only
the time spent connecting to and receiving a response from the
database.  Especially when response are large, there can often be a
great deal of Python processing overhead to marshall the data from the
database into Django objects that is not accounted for in these
numbers.

## Blueslip frontend error reporting

We have a custom library, called `blueslip` (named after the form used
at MIT to report problems with the facilities), that takes care of
reporting JavaScript errors.  In production, this means emailing the
server administrators (though the setting controlling this,
`BROWSER_ERROR_REPORTING`, is disabled by default, since most problems
are unlikely to be addressable by a system administrator, and it's
very hard to make JavaScript errors not at least somewhat spammy due
to the variety of browser versions and sets of extensions that someone
might use).  In development, this means displaying a highly visible
overlay over the message view area, to make exceptions in testing a
new feature hard to miss.

* Blueslip is implemented in `static/js/blueslip.js`.
* In order to capture essentially any error occurring in the browser,
blueslip does the following:
  * Wraps every function passed into `$.ready()`, i.e., every
  on-webapp-startup method used by Zulip.
  * Wraps every jQuery AJAX request handler used by Zulip.
  * Wraps every function passed into `$.on()`, i.e. all event
  handlers declared in Zulip.
  * Declares a default browser exception handler.
  * Has methods for being manually triggered by Zulip JavaScript code
    for warnings and assertion failures.
* Blueslip keeps a log of all the notices it has received during a
  browser session, and includes them in reports to the server, so that
  one can see cases where exceptions chained together.  You can print
  this log from the browser console using `blueslip.get_log()`.

Blueslip supports several error levels:
* `blueslip.fatal`: For fatal errors that cannot be easily recovered
  from.  We try to avoid using it, since it kills the current JS
  thread, rather than returning execution to the caller.  Unhandled
  exceptions in our JS code are treated like `blueslip.fatal`.
* `blueslip.error`: For logging of events that are definitely caused
  by a bug and thus sufficiently important to be reported, but where
  we can handle the error without creating major user-facing problems
  (e.g. an exception when handling a presence update).
* `blueslip.warn`: For logging of events that are a problem but not
  important enough to send an email about in production.  They are,
  however, highlighted in the JS console in development.
* `blueslip.log` (and `blueslip.info`): Logged to the JS console in
  development and also in the blueslip log in production.  Useful for
  data that might help discern what state the browser was in during an
  error (e.g. whether the user was in a narrow).
* `blueslip.debug`: Similar to `blueslip.log`, but are not printed to
  the JS console in development.

## Frontend performance reporting

In order to make it easier to debug potential performance problems in
the critically latency-sensitive message sending code pathway, we log
and report to the server the following whenever a message is sent:

* The time the user triggered the message (aka the start time).
* The time the `send_message` response returned from the server.
* The time the message was received by the browser from the
  `get_events` protocol (these last two race with each other).
* Whether the message was locally echoed.
* If so, whether there was a disparity between the echoed content and
  the server-rendered content, which can be used for statistics on how
  effective our [local echo system](../subsystems/markdown.html) is.

The code is all in `zerver/lib/report.py` and `static/js/sent_messages.js`.

We have similar reporting for the time it takes to narrow / switch to
a new view:

* The time the action was initiated
* The time when the updated message feed was visible to the user
* The time when the browser was idle again after switching views
  (intended to catch issues where we generate a lot of deferred work).

[django-errors]: https://docs.djangoproject.com/en/1.11/howto/error-reporting/
[python-logging]: https://docs.python.org/3/library/logging.html
[django-logging]: https://docs.djangoproject.com/en/1.11/topics/logging/
[sentry]: https://sentry.io
