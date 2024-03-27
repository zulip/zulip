# Construct a narrow

A **narrow** is a set of filters for Zulip messages, which can be based on various factors like sender, stream, topic, search keywords, etc. Narrows are extensively used in the Zulip API, particularly in the API for fetching messages.

It is crucial to consider adding an `is:unread` filter to your narrow when adding the "read" flag. The Zulip server has a database index for unread messages, and including the `is:unread` filter optimizes the performance of fetching messages. This optimization is essential for any full-featured client, although it may not be obvious initially.

The algorithm for encoding a search as a narrow is best explained with an example. Consider the following search query (as it would be entered in the Zulip web app's search box), filtering for messages sent to stream `announce`, not sent by `iago@zulip.com`, and containing the words `cool` and `sunglasses`:

```
stream:announce -sender:iago@zulip.com cool sunglasses
```

This query would be JSON-encoded for use in the Zulip API
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

The Zulip help center article on [searching for messages](/help/search-for-messages)
documents the majority of the search/narrow options supported by the
Zulip API.

Note that many narrows, including all that lack a `stream` or `streams`
operator, search the current user's personal message history. See
[searching shared history](/help/search-for-messages#searching-shared-history)
for details.

**Changes**: In Zulip 7.0 (feature level 177), support was added
for three filters related to direct messages: `is:dm`, `dm` and
`dm-including`. The `dm` operator replaced and deprecated the
`pm-with` operator. The `is:dm` filter replaced and deprecated
the `is:private` filter. The `dm-including` operator replaced and
deprecated the `group-pm-with` operator.

The `dm-including` and `group-pm-with` operators return slightly
different results. For example, `dm-including:1234` returns all
direct messages (1-on-1 and group) that include the current user
and the user with the unique user ID of `1234`. On the other hand,
`group-pm-with:1234` returned only group direct messages that included
the current user and the user with the unique user ID of `1234`.

Both `dm` and `is:dm` are aliases of `pm-with` and `is:private`
respectively, and return the same exact results that the deprecated
filters did.

## Narrows that use IDs

### Message IDs

The `near` and `id` operators, documented in the help center, use message
IDs for their operands.

* `near:12345`: Search messages around the message with ID `12345`.
* `id:12345`: Search for only message with ID `12345`.

The message ID operand for the `id` operator may be encoded as either a
number or a string. The message ID operand for the `near` operator must
be encoded as a string.

**Changes**: Prior to Zulip 8.0 (feature level 194), the message ID
operand for the `id` operator needed to be encoded as a string.


```json
[
    {
        "operator": "id",
        "operand": 12345
    }
]
```

### Stream and user IDs

There are a few additional narrow/search options (new in Zulip 2.1)
that use either stream IDs or user IDs that are not documented in the
help center because they are primarily useful to API clients:

* `stream:1234`: Search messages sent to the stream with ID `1234`.
* `sender:1234`: Search messages sent by user ID `1234`.
* `dm:1234`: Search the direct message conversation between
  you and user ID `1234`.
* `dm:1234,5678`: Search the direct message conversation between
  you, user ID `1234`, and user ID `5678`.
* `dm-including:1234`: Search all direct messages (1-on-1 and group)
  that include you and user ID `1234`.

!!! tip ""

    A user ID can be found by [viewing a user's profile][view-profile]
    in the web or desktop apps. A stream ID can be found when [browsing
    streams][browse-streams] in the web app via the URL.

The operands for these search options must be encoded either as an
integer ID or a JSON list of integer IDs. For example, to query
messages sent by a user 1234 to a direct message thread with yourself,
user 1234, and user 5678, the correct JSON-encoded query is:

```json
[
    {
        "operator": "dm",
        "operand": [1234, 5678]
    },
    {
        "operator": "sender",
        "operand": 1234
    }
]
```

[view-profile]: /help/view-someones-profile
[browse-streams]: /help/browse-and-subscribe-to-streams
