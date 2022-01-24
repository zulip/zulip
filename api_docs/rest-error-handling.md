# Error handling

Zulip's API will always return a JSON format response.
The HTTP status code indicates whether the request was successful
(200 = success, 40x = user error, 50x = server error).  Every response
will contain at least two keys: `msg` (a human-readable error message)
and `result`, which will be either `error` or `success` (this is
redundant with the HTTP status code, but is convenient when printing
responses while debugging).

For some common errors, Zulip provides a `code` attribute.  Where
present, clients should check `code`, rather than `msg`, when looking
for specific error conditions, since the `msg` strings are
internationalized (e.g. the server will send the error message
translated into French if the user has a French locale).

Each endpoint documents its own unique errors; documented below are
errors common to many endpoints:

{generate_code_example|/rest-error-handling:post|fixture}

## Ignored Parameters

In JSON success responses, all Zulip REST API endpoints may return
an array of parameters sent in the request that are not supported
by that specific endpoint.

While this can be expected, e.g. when sending both current and legacy
names for a parameter to a Zulip server of unknown version, this often
indicates either a bug in the client implementation or an attempt to
configure a new feature while connected to an older Zulip server that
does not support said feature.

{generate_code_example|/settings:patch|fixture}
