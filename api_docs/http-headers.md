# HTTP headers

This page documents the HTTP headers used by the Zulip API.

Most important is that API clients authenticate to the server using
HTTP Basic authentication. If you're using the official [Python or
JavaScript bindings](/api/installation-instructions), this is taken
care of when you configure said bindings.

Otherwise, see the `curl` example on each endpoint's documentation
page, which details the request format.

Documented below are additional HTTP headers and header conventions
generally used by Zulip:

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
`#integrations` in the [Zulip development
community](https://zulip.com/development-community).

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

[rate-limiting-rules]: https://zulip.readthedocs.io/en/latest/production/security-model.html#rate-limiting
