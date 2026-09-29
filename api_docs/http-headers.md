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

This optional header lets a client safely retry a request that isn't
idempotent, like sending a message, without the server doing its work
twice. While [RFC 9110][rfc9110-retries] states that "a proxy MUST
NOT automatically retry non-idempotent requests," proxies regularly
do so, leading to problems like double-sent messages.

A request is identified by its user and idempotency key. The client
generates a random (version 4) UUID and includes it in the
`Idempotency-Key` request header, in the standard hyphenated format
with either uppercase or lowercase letters:

```
Idempotency-Key: 8e03978e-40d5-43e8-bc93-6894a57f9324
```

The server also accepts the UUID in double quotes
(`"8e03978e-40d5-43e8-bc93-6894a57f9324"`), which is the format that
the [IETF draft][idempotency-key-draft] for this header specifies. It
rejects values in any other format with a `400 Bad Request` error
whose `code` is `INVALID_IDEMPOTENCY_KEY`. That includes other ways
of writing a UUID, like without hyphens or with a `urn:uuid:` prefix.

Once the server has cached the response to a request, a later request
from that user with the same header gets that response, without the
server doing the work again. The sections below describe which
responses are cached, and for how long.

**Changes**: New in Zulip 14.0 (feature level ZF-89b894).

### Supported endpoints

Only endpoints which explicitly document support for this protocol
honor the `Idempotency-Key` header; currently, that's only
[`POST /messages`](/api/send-message). The `Idempotency-Key` header
is silently ignored on all other requests.

### Replayed responses

When a request is served from the idempotency cache, the server
replays the original response body and status code. Response headers
are regenerated for each request and may differ from the original --
in particular, rate-limiting headers reflect the current state, and
repeated requests count against rate limits as normal.

Before looking up the cached response, the server authenticates the
request and checks some of its parameters, like whether they're
well-formed. As a result, a replay can get an error even if the
original request succeeded, for instance if the user's API key has
since been regenerated. Other checks, like whether the user can post
in the channel, are part of the cached response.

### Concurrent requests

If a request with the same `Idempotency-Key` is already being
concurrently processed, but its results are not yet available, the
client may receive a `409 Conflict` error whose `code` is
`IDEMPOTENCY_KEY_IN_USE`. Some endpoints use `409` for other errors,
so clients should check for this `code` rather than the status.

Clients _should_ retry after a short delay with the same
`Idempotency-Key`. The retry gets the cached response once the
original request finishes, or this error again if it is still
running. If the original request ended without caching a response
-- for instance, because it failed with a 5xx error, or the backend
processing it crashed -- the retry is processed from scratch.

### Retrying requests

To retry a request, a client _should_ use the same `Idempotency-Key`
if the request:

- Got no response, for instance because of a network error or a
  timeout.
- Failed with a 5xx error. The server may or may not have completed
  the work. If it did, the retry gets the cached response; otherwise,
  the retry is processed from scratch.
- Failed with an `IDEMPOTENCY_KEY_IN_USE` error, or with an
  authentication or [rate-limiting](#rate-limiting-response-headers)
  error. The server doesn't cache these errors.

After any other 4xx error, a client _must_ use a new
`Idempotency-Key` to try again. The server may cache such an error
like a successful result, and return it for later requests with the
same key, even if they would now succeed -- for instance, because the
user has since been given permission to post in the channel.

### Key reuse across requests

The server does not currently compare the parameters of requests with
the same `Idempotency-Key`, and will return the cached response for
the original request even if a subsequent request with the same key
carries different parameters -- which may be nonsensical in the new
context. This behavior is not guaranteed: the server may begin
validating parameter consistency in the future, at which point
mismatched reuse will return an error.

Clients _must_ therefore use a new `Idempotency-Key` for every
request other than the retries listed in
[Retrying requests](#retrying-requests).

### Expiration

The server caches the response for a given `Idempotency-Key` for at
least 24 hours after it receives the first request with that key, and
may cache it for longer. Clients should only rely on a retry getting
the cached response within those 24 hours; a later retry may be
processed from scratch.

[rate-limiting-rules]: https://zulip.readthedocs.io/en/latest/production/securing-your-zulip-server.html#rate-limiting
[integrations-channel]: https://chat.zulip.org/#narrow/channel/127-integrations/
[mdn-auth-headers]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Authorization
[mdn-basic-auth]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Authorization#basic_authentication_2
[rfc9110-retries]: https://www.rfc-editor.org/rfc/rfc9110#section-9.2.2
[idempotency-key-draft]: https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
