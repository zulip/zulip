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

Each endpoint documents its own unique errors; below, we document
errors common to many endpoints:

{generate_code_example|/rest-error-handling:post|fixture}

The `retry-after` parameter in the response indicates how many seconds
the client must wait before making additional requests.

To help clients avoid exceeding rate limits, Zulip sets the following
HTTP headers in all API responses:

* `X-RateLimit-Remaining`: The number of additional requests of this
  type that the client can send before exceeding its limit.
* `X-RateLimit-Limit`: The limit that would be applicable to a client
  that had not made any recent requests of this type. This is useful
  for designing a client's burst behavior so as to avoid ever reaching
  a rate limit.
* `X-RateLimit-Reset`: The time at which the client will no longer
  have any rate limits applied to it (and thus could do a burst of
  `X-RateLimit-Limit` requests).

Zulip's rate limiting rules are configurable, and can vary by server
and over time. The default configuration currently limits:

* Every user is limited to 200 total API requests per minute.
* Separate, much lower limits for authentication/login attempts.

When the Zulip server has configured multiple rate limits that apply
to a given request, the values returned will be for the strictest
limit.

**Changes**: The `code` field in the response is new in Zulip 4.0
(feature level 36).
