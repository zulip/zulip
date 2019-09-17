# Construct a narrow

A **narrow** is a set of filters for Zulip messages, that can be based
on many different factors (like sender, stream, topic, search
keywords, etc.).  Narrows are used in various places in the the Zulip
API (most importantly, in the API for fetching messages).

It is simplest to explain the algorithm for encoding a search as a
narrow using a single example.  Consider the following search query
(written as it would be entered in the Zulip webapp's search box).  It
filters for messages sent on stream `announce`, not sent by
`iago@zulip.com`, and containing the phrase `cool sunglasses`:

```
stream:announce -sender:iago@zulip.com cool sunglasses
```

This query would be JSON-encoded for use in the Zulip API using JSON
as a list of simple objects, as follows:

```json
[
    {
        "operator": "stream",
        "operand": "announce"
    },
    {
        "operator": "sender",
        "operand": "iago@zulip.com",
        "negated": true
    },
    {
        "operator": "search",
        "operand": "cool sunglasses"
    }
]
```

The full set of search/narrowing options supported by the Zulip API is
documented in [the Zulip Help Center article on
search](/help/search-for-messages).  There are a few additional
options, new in Zulip 2.1, that we don't document there because they
are primarily useful to API clients:

* `sender:1234`: Search messages sent by user ID `1234`.
* `stream:1234`: Search messages sent to the stream with ID `123`.
* `pm-with:1234`: Search the private message conversation between
  you and user ID `1234`.
* `pm-with:1234,5678`: Search the private message conversation between
  you, user ID `1234`, and user ID `5678`.
* `group-pm-with:1234`: Search all (group) private messages that
  include user ID `1234`.
* `pm-with:1234,5678`: Search all (group) private messages that
  include user ID `1234` and user ID `5678`.

The operands for these search options must be encoded either as an
integer ID or a JSON list of integer IDs.  For example, to query
messages sent by a user 1234 to a PM thread with yourself, user 1234,
and user 5678, the correct JSON-encoded query is:

```json
[
    {
        "operator": "pm-with",
        "operand": [1234, 5678]
    },
    {
        "operator": "sender",
        "operand": 1234
    }
]
```
