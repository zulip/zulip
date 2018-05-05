# Error Handling

Zulip's API will always return a JSON format response.  Like any good
API, the HTTP status code indicates whether the request was successful
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

Each endpoint documents its own unique errors; below, we document
errors common to many endpoints:

## Invalid API key

A typical failed JSON response for when the API key is invalid:

{generate_code_example|invalid-api-key|fixture}

## Missing request argument(s)

A typical failed JSON response for when a required request argument
is not supplied:

{generate_code_example|missing-request-argument-error|fixture}

## User not authorized for query

A typical failed JSON response for when the user is not authorized
for a query:

{generate_code_example|user-not-authorized-error|fixture}
