# HTTP headers

This page documents the HTTP headers used by the Zulip API.

!!! tip ""

    Full details of the HTTP requests are given in the `curl` example
    on each endpoint's documentation page. You can access curl's
    documentation at [`man curl`](https://curl.se/docs/manpage.html).

## The `Authorization` header

Most important is that API clients authenticate to the server using
HTTP Basic authentication. If you're using the official [Python or
JavaScript bindings](/api/installation-instructions), this is taken
care of when you configure said bindings.

Otherwise, to authenticate an API request:

- Use HTTP `Basic` authentication, which is described [here][mdn-auth-headers].
  This means sending an HTTP header named `Authorization`, with your
  credentials [in a certain format][mdn-basic-auth].

- For `Basic` authentication credentials in the Zulip API, a "username"
  takes the form of an email address, and a "password" takes the form of
  an API key. In the `curl` example for each endpoint, this is shown as:
  `-u EMAIL_ADDRESS:API_KEY`.

- A bot's credentials can be obtained through the web and desktop apps'
  [bot management UI](/help/manage-a-bot) or by [downloading the bot's
  `zuliprc` file](/api/api-keys#download-a-zuliprc-file).

- See [fetch an API key (production)](/api/fetch-api-key) for the
  password-based authentication flow for getting a user's credentials.

## The `User-Agent` header

Clients are not required to pass a `User-Agent` HTTP header, but we
highly recommend doing so when writing an integration. It's easy to do
and it can help save time when debugging issues related to an API
client.

If provided, the Zulip server will parse the `User-Agent` HTTP header
in order to identify specific clients and integrations. This
information is used by the server for logging, [usage
statistics](/help/analytics), and on rare occasions, for
backwards-compatibility logic to preserve support for older versions
of official clients.

Official Zulip clients and integrations use a `User-Agent` that starts
with something like `ZulipMobile/20.0.103 `, encoding the name of the
application and it's version.

Zulip's official API bindings have reasonable defaults for
`User-Agent`. For example, the official Zulip Python bindings have a
default `User-Agent` starting with `ZulipPython/{version}`, where
`version` is the version of the library.

You can give your bot/integration its own name by passing the `client`
parameter when initializing the Python bindings. For example, the
official Zulip Nagios integration is initialized like this:

``` python
client = zulip.Client(
    config_file=opts.config, client=f"ZulipNagios/{VERSION}"
)
```

If you are working on an integration that you plan to share outside
your organization, you can get help picking a good name in
[#integrations][integrations-channel] in the [Zulip development
community](https://zulip.com/development-community/).

## Rate-limiting response headers

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

[Zulip's rate limiting rules are configurable][rate-limiting-rules],
and can vary by server and over time. The default configuration
currently limits:

* Every user is limited to 200 total API requests per minute.
* Separate, much lower limits for authentication/login attempts.

When the Zulip server has configured multiple rate limits that apply
to a given request, the values returned will be for the strictest
limit.

## The `Idempotency-Key` request header

This header is used as the identifier of a request in our idempotency
system; its use is optional.

The goal of this system is to ensure idempotency for non-idempotent
HTTP methods (i.e., `POST` requests).  While [RFC
9110][rfc9110-retries] states that "a proxy MUST NOT automatically
retry non-idempotent requests," proxies regularly do so, leading to
problems like double-sent messages.

A request is uniquely identified by its realm, user, and idempotency
key.  The client generates a UUID and includes it in the
`Idempotency-Key` request header; the server validates that the value
is a well-formed UUID and rejects malformed values with a `400 Bad
Request` response.  A matching request from that user with that same
header will see the same response body, and the server will perform
the work at most once.

### Supported endpoints

Only endpoints which explicitly document support for this protocol
honor the `Idempotency-Key` header; all such endpoints use the `POST`
method.  The `Idempotency-Key` header is silently ignored on all other
requests.

### Replayed responses

When a request is served from the idempotency cache, the server
replays the original response body and status code.  Response headers
are regenerated for each request and may differ from the original --
in particular, rate-limiting headers reflect the current state, and
repeated requests count against rate limits as normal.

### Concurrent requests

If a request with the same `Idempotency-Key` is already being
concurrently processed, but its results are not yet available, the
client receives a `409 Conflict` response.  This use of `409` is
specific to the idempotency system and indicates a duplicate in-flight
key, not a resource state conflict.  Clients _may_ retry the request
with the same `Idempotency-Key` to see the results of the request (or
a `409` again if it is still not complete).

If a backend processing a request crashes before producing a result,
a subsequent request with the same key will begin processing from
scratch rather than receiving a `409`.

### Error results

Except for `409 Conflict` responses, a client _must_ retry 4xx results
with a new `Idempotency-Key`, even if no parameters are changed -- for
instance, the user's authorization may have changed on the server.
The server caches 4xx results for the same 24-hour window as
successful results (see [Expiration](#expiration)), in order to absorb
network-level retries of the same key and save server-side work.

A client _should_ retry 5xx results with the same `Idempotency-Key`,
as the server may or may not have completed the work.  If the original
work did complete, the retry returns the cached result; if it did not,
the retry begins processing from scratch.

### Key reuse across requests

The server does not currently compare the endpoint or request
parameters associated with an `Idempotency-Key`, and will return the
cached response for the original request even if a subsequent request
with the same key targets a different endpoint or carries different
parameters -- which may be nonsensical in the new context.  This
behavior is not guaranteed: the server may begin validating endpoint
and parameter consistency in the future, at which point mismatched
reuse will return an error.

Clients _must_ therefore generate a new `Idempotency-Key` for every
request that is not an intentional retry of a prior `409` or 5xx
response.

### Expiration

The server caches the results for a given `Idempotency-Key` for at
least 24 hours after the first request referencing that key is
received; servers may opt to cache them for longer.


[rate-limiting-rules]: https://zulip.readthedocs.io/en/latest/production/securing-your-zulip-server.html#rate-limiting
[integrations-channel]: https://chat.zulip.org/#narrow/channel/127-integrations/
[mdn-auth-headers]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Authorization
[mdn-basic-auth]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Authorization#basic_authentication_2
[rfc9110-retries]: https://www.rfc-editor.org/rfc/rfc9110#section-9.2.2
