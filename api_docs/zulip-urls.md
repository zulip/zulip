# Zulip URLs

This page details how to properly construct and parse the URLs that
the Zulip web app uses for various types of views.

Because other clients needs to be able to resolve and process these
links in order to implement equivalent behavior that navigates
directly in say the mobile apps, it's important to have a clear
specification of exactly how these URLs work.

Essentially all of the data is encoded in the URL fragment (`#`) part
of a URL; the protocol, host and path will just be the canonical URL
for the Zulip server (In these examples,
`https://zulip.example.com/`).

## Message feed views

Most links in Zulip are to message feed views, and for that reason
these have the most developed syntax and legacy behavior.

Message feed URLs always start with `#narrow/`, follow by one or more
[search operator/operand pairs](/api/construct-narrow), separated by
`/`s. The operator may be negated by putting a `-` at the start of
it. For example:

`https://zulip.example.com/#narrow/is/starred/sender/17/-channel/14`

is the feed of starred messages sent by user ID to everywhere but
channel 14. The search documentation covers the valid operators and
their meaning.

See also the relevant [message formatting
documentation](/api/message-formatting) for details on Markdown
representations of Zulip-internal links that will be translated into
HTML containing links that use these URLs.

Here, we describe some special encoding rules.

### Operand encoding and decoding

Strings in operands are URL-encoded, and then additional substitution
rules are applied to avoid over-zealous browser handling of certain
characters in the URL fragment:

- `%` => `.`
- `(` => `.28`
- `)` => `.29`
- `.` => `.2E`

They can decoded by applying the reverse transformation: Replace all
`.` characters with `%`, and then do standard URL-decoding.

### Encoding channels

Channel operands must be encoded in one of the two modern fully
supported formats:

- `42`: Just the ID of the channel. Clients should simply parse the
  channel ID to look up the channel, which is of course not guaranteed
  to be accessible to the acting user or even exist.
- `42-channel-name`. The ID of the channel, with a human-readable hint
  of the channel name. Clients generating Zulip URLs are recommended
  to include channel name hints where there is a readable URL-encoding
  of the channel name, but to skip doing so for channel names written
  in non-ascii languages or where otherwise the slug would not make
  the URL nicer for humans. Clients must parse this format by
  discarding everything after the `-` and treating it identically to
  the simpler integer-only format. Note that means nothing enforces
  that the string have anything to do with the channel name;
  functionally, it just an optional hint.

These two formats allow Zulip URLs to stably refer to a specific
channel, even though channels can be renamed, while still allowing the
URLs to have user-friendly name hints most of the time.

There is an additional legacy format that was used prior to 2018 that
clients are required to support:

- `channel-name`: Legacy format of just the channel name, URL-encoded
  and with spaces replaced with dashes. The legacy format should never
  take precedence over the modern format, so a link with
  `2016-election` as the slug must be parsed as the channel with ID
  2016, even if theoretically it could have been originally intended
  as referring to a channel named `2016 election`.

Clients are not recommended to ever generate this legacy format.

## zulip:// links for mobile login

Zulip's single-sign on login process for the mobile app ends with a
redirect to `zulip://login` with the following query parameters:

- `email`: The email address for the authenticated account.
- `otp_encrypted_api_key`: The API key for the client, encrypted using
  the `mobile_flow_otp` that the client provided when initiating the
  login attempt.
- `realm`: The full URL of the Zulip organization.
- `user_id`: The Zulip user ID for the authenticated account.

**Changes**: The `user_id` field was added to the set of included
query parameters in Zulip 5.0 (feature level 128).

## Related articles

* [Message formatting API](/api/message-formatting)
* [Construct a narrow](/api/construct-narrow) for search.
* [Markdown formatting help](/help/format-your-message-using-markdown)
* [Send a message](/api/send-message)

