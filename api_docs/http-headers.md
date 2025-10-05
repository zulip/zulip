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

* Every user is limited to 200 total API requests per minute, and 2000
  total API requests per hour.
* Separate, much lower limits for authentication/login attempts.

When the Zulip server has configured multiple rate limits that apply
to a given request, the values returned will be for the strictest
limit.

[rate-limiting-rules]: https://zulip.readthedocs.io/en/latest/production/securing-your-zulip-server.html#rate-limiting
[integrations-channel]: https://chat.zulip.org/#narrow/channel/127-integrations/


## The `Idempotency-Key` request header
The header we use as the identifier of a request in our idempotency system; technically, we identify a request by 3 fields (realm, user, and key), however, the key is the relevant part in this documentation.

The goal of this system is to ensure idempotency for non-idempotent HTTP methods (e.g., `POST` request). The client generates a UUID and includes it in the `Idempotency-Key` request header. The server processes the request normally, then caches that request's successful or failed `non-5xx` response, using its key as the identifier. Requests with a key that the server saw before get the cached (successful/failed) response of the previous request, effectively preventing duplicate work.

The system only works when the operation, we want to be idempotent, is within the scope of an endpoint.

Currently, applied only to sending a message via `POST` requests to `/json/messages`

**Note:** `Idempotency-Key` header is optional and the server still proceeds normally if the header is omitted.

### Backend details
The main logic of this system is implemented in `zerver/lib/idempotent_request.py`. It has 2 decorators called in order: `@idempotent_endpoint` then `@idempotent_work`.

#### `@idempotent_endpoint`
Currently decorating the view `send_message_backend`.

Decorates a view and the 1st entrance to this system; explicitly says the whole system is relevant ONLY for a request hitting an endpoint.

This decorator is responsible for:

1. Ensuring the key is a valid UUID, without enforcing a specific version.
2. Inserting a row, initially representing a not-yet-attempted work. And it expects an already existing row in case of duplicate requests.
3. Catching and caching any raised non-transient json error,
and marks the work as failed.

#### `@idempotent_work`
Currently decorating `do_send_messages`.

Decorates the actual work we want to ensure idempotency for, and to more finely control the start and the end of a transaction.

It handles concurrency by locking the correspodning row during the transaction, ensuring only one request is doing the work at a given time. Will raise `LockedError` if another request with the same key is concurrently in progress.

We have 3 cases:

1. **New work**: proceeds with the work and caches the result.
2. **Duplicate succeeded work**: returns the cached result.
3. **Duplicate failed work**: raises the cached error (non-transient error).


### Retried vs Replayed request
#### Replayed request
Something (a buggy network, a browser, or a proxy) somewhere along the request path to the server **incorrectly** replays the `HTTP` request. In this case, we never want to change the key, and we wouldn't be able to change it anyway, since the request would have already left the client. **This is the main duplicate request issue (but not the only) that this system solves**.

#### Retried request
An aware client (e.g., web app, mobile app) **intentinoally** retrying the request upon receiving an error (`5xx` or `4xx`). It's the client's responsibility to decide whether to keep or change the key when retrying the request. The client should handle `4xx` and `5xx` errors differently:

### Expected vs Unexpected failure
In the context of this system, we differentiate between `4xx` and `5xx`, and we handle them differently:

#### 4xx validation error
**Something expected**, the server handles the request correctly and returns a response to the client, **but the request itself is invalid** and therefore refused. This can happen in case the client sends invalid data or because the server's validation (e.g., checking user's permission to post to a stream ) for that request changes. In this case, retrying the exact same request wouldn't make much sense because something in that invalid request must change, so the client should first modify the request and retries it with a **different key** with the hope it will be valid. **Changing the key** is important to avoid getting the cached response of the previous request.

#### 5xx Server/Network error
**Something unexpected** occurs somewhere in the request's cycle preventing the client from receiving the expected response:

1. A network error preventing the request from reaching the server or the response from reaching the client.
2. A server error/crash before or after completing the work.

In either case, the client has no idea of whether the work was completed or not because something unexpectedly failed (as opposed to an expected validation error) and should be retried as it is. Therefore, the client **must** retry the same request using the **same key**.


**Note:** Zulip web app retries the request using the **same** key in case of `5xx` errors, but **changes** the key in case of `4xx` errors.


### Cases
We have **8** different cases:

#### 1. Successful request
Our happy and most common case. The server processes the request normally, caches its successful response, any incoming duplicate requests receive that same cached response, effectively achieving idempotency and preventing redoing of the work.

#### 2. Early validation error
When a request fails validation early before the actual work (i.e. [@idempotent_work](#idempotent_work)) is attempted. Some requests (e.g., POST `/json/messages`) are validated early before their corresponding work (typically a transactional code) is attempted.
In this case, we still cache the response error (because of how the system is designed), **but** duplicate requests would get validated exactly as the original request because we never get to [@idempotent_work](#idempotent_work) which would check for the cached response, deserialize, and return it.

#### 3. Validation error during the work
When a request fails validation within the scope of [@idempotent_work](#idempotent_work). In this case we catch the error and cache its response, so duplicate requests would get that cached response (as opposed to the previous case) and we wouldn't need to redo the validation.

#### 4. Different requests having the same key
When a confused client reuses the same key for a different request.
Currently, we identify a request by its key and not by its parameters, so in this case, the 2nd different request will receive the cached response of the 1st one. It's the client's responsibility to change the key when issuing a different request.

#### 5. Validation changes for the same request
When server validation for the same request changes. For example, a user's permission to post to a channel changes, between the first and retried request.

**a. Request initially fails validation but passes it on retry.**

In this case, the client should retry the request with a different key (see [4xx validation error](#4xx-validation-error)) to get the new response that reflects the new validation, otherwise, retrying with the same key would return the old cached response reflecting the old validation.  

**b. Request initially passes validation but fails on retry.**

Similar to previous case, **except** when the failed validation is [Early validation error](#2-early-validation-error), in which case retrying with the same or a different key would have no effect, and the client would get the response (un-cached) that reflects the new validation anyway.

#### 6. Server/network error before attempting/completing the work
A network error preventing the request from reaching the server or a server error after receiving the request but before completing the work. Since the work was never completed, it makes no difference to idempotency whether the client retries the request with the same or a different key. **However** the client has no idea of that (it just receives an ambiguous `5xx` error), and should ideally retry the request with the **same** key in case the work was actually completed (next case).

#### 7. Server/network error after successfully completing the work
This is a special case where the request is processed and cached successfully
by the server, but failed (due to [5xx Server/Network error](#5xx-servernetwork-error)) to reach the client. Like the previous case, the client doesn't know whether the request was successful or not, and should should retry the request with the same key to get the result of the previously **unreceived** successful response.

#### 8. Concurrent request
If a server receives a request while another request (with the same key) is doing the work within the scope of [@idempotent_work](#idempotent_work), that 2nd request will be refused and will receive a `409` conflict error response.
