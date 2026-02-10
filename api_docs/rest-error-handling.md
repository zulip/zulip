# Error handling

Zulip's API will always return a JSON format response.
The HTTP status code indicates whether the request was successful
(200 = success, 4xx = user error, 5xx = server error).

Every response, both success and error responses, will contain at least
two keys:

- `msg`: an internationalized, human-readable error message string.

- `result`: either `"error"` or `"success"`, which is redundant with the
  HTTP status code, but is convenient when print debugging.

Every error response will also contain an additional key:

- `code`: a machine-readable error string, with a default value of
  `"BAD_REQUEST"` for general errors.

Clients should always check `code`, rather than `msg`, when looking for
specific error conditions. The string values for `msg` are
internationalized (e.g., the server will send the error message
translated into French if the user has a French locale), so checking
those strings will result in buggy code.

!!! tip ""

     If a client needs information that is only present in the string value
     of `msg` for a particular error response, then the developers
     implementing the client should [start a conversation here][api-design]
     in order to discuss getting a specific error `code` and/or relevant
     additional key/value pairs for that error response.

In addition to the keys described above, some error responses will
contain other keys with further details that are useful for clients. The
specific keys present depend on the error `code`, and are documented at
the API endpoints where these particular errors appear.

**Changes**: Before Zulip 5.0 (feature level 76), all error responses
did not contain a `code` key, and its absence indicated that no specific
error `code` had been allocated for that error.

## Common error responses

Documented below are some error responses that are common to many
endpoints:

{generate_code_example|/rest-error-handling:post|fixture}

## Ignored Parameters

In JSON success responses, all Zulip REST API endpoints may return
an array of parameters sent in the request that are not supported
by that specific endpoint.

While this can be expected, e.g., when sending both current and legacy
names for a parameter to a Zulip server of unknown version, this often
indicates either a bug in the client implementation or an attempt to
configure a new feature while connected to an older Zulip server that
does not support said feature.

{generate_code_example|/settings:patch|fixture}

[api-design]: https://chat.zulip.org/#narrow/channel/378-api-design
