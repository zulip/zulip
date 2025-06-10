# Construct a narrow

A **narrow** is a set of filters for Zulip messages, that can be based
on many different factors (like sender, channel, topic, search
keywords, etc.). Narrows are used in various places in the Zulip
API (most importantly, in the API for fetching messages).

It is simplest to explain the algorithm for encoding a search as a
narrow using a single example. Consider the following search query
(written as it would be entered in the Zulip web app's search box).
It filters for messages sent to channel `announce`, not sent by
`iago@zulip.com`, and containing the words `cool` and `sunglasses`:

```
channel:announce -sender:iago@zulip.com cool sunglasses
```

This query would be JSON-encoded for use in the Zulip API using JSON
as a list of simple objects, as follows:

```json
[
    {
        "operator": "channel",
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

Note that many narrows, including all that lack a `channel` or `channels`
operator, search the current user's personal message history. See
[searching shared history](/help/search-for-messages#searching-shared-history)
for details.

Clients should note that the `is:unread` filter takes advantage of the
fact that there is a database index for unread messages, which can be an
important optimization when fetching messages in certain cases (e.g.,
when [adding the `read` flag to a user's personal
messages](/api/update-message-flags-for-narrow)).

Note: When the value of `realm_empty_topic_display_name` found in
the [POST /register](/api/register-queue) response is used as an operand
for the `"topic"` operator in the narrow, it is interpreted
as an empty string.

## Changes

* In Zulip 10.0 (feature level 366), support was added for a new
  `is:muted` operator combination, matching messages in topics and
  channels that the user has [muted](/help/mute-a-topic).

* Before Zulip 10.0 (feature level 334), empty string was not a valid
  topic name for channel messages.

* In Zulip 9.0 (feature level 271), support was added for a new filter
  operator, `with`, which uses a [message ID](#message-ids) for its
  operand, and is designed for creating permanent links to topics.

* In Zulip 9.0 (feature level 265), support was added for a new
  `is:followed` filter, matching messages in topics that the current
  user is [following](/help/follow-a-topic).

* In Zulip 9.0 (feature level 250), support was added for two filters
  related to stream messages: `channel` and `channels`. The `channel`
  operator is an alias for the `stream` operator. The `channels`
  operator is an alias for the `streams` operator. Both `channel` and
  `channels` return the same exact results as `stream` and `streams`
  respectively.

* In Zulip 9.0 (feature level 249), support was added for a new filter,
  `has:reaction`, which returns messages that have at least one [emoji
  reaction](/help/emoji-reactions).

* In Zulip 7.0 (feature level 177), support was added for three filters
  related to direct messages: `is:dm`, `dm` and `dm-including`. The
  `dm` operator replaced and deprecated the `pm-with` operator. The
  `is:dm` filter replaced and deprecated the `is:private` filter. The
  `dm-including` operator replaced and deprecated the `group-pm-with`
  operator.

    * The `dm-including` and `group-pm-with` operators return slightly
      different results. For example, `dm-including:1234` returns all
      direct messages (1-on-1 and group) that include the current user
      and the user with the unique user ID of `1234`. On the other hand,
      `group-pm-with:1234` returned only group direct messages that
      included the current user and the user with the unique user ID of
      `1234`.

    * Both `dm` and `is:dm` are aliases of `pm-with` and `is:private`
      respectively, and return the same exact results that the
      deprecated filters did.

## Narrows that use IDs

### Message IDs

The `id` and `with` operators use message IDs for their operands. The
message ID operand for these two operators may be encoded as either a
number or a string.

* `id:12345`: Search for only the message with ID `12345`.
* `with:12345`: Search for the conversation that contains the message
  with ID `12345`.

The `id` operator returns the message with the specified ID if it exists,
and if it can be accessed by the user.

The `with` operator is designed to be used for permanent links to
topics, which means they should continue to work when the topic is
[moved](/help/move-content-to-another-topic) or
[resolved](/help/resolve-a-topic). If the message with the specified
ID exists, and can be accessed by the user, then it will return
messages with the `channel`/`topic`/`dm` operators corresponding to
the current conversation containing that message, replacing any such
operators included in the original narrow query.

If no such message exists, or the message ID represents a message that
is inaccessible to the user, this operator will be ignored (rather
than throwing an error) if the remaining operators uniquely identify a
conversation (i.e., they contain `channel` and `topic` terms or `dm`
term). This behavior is intended to provide the best possible
experience for links to private channels with protected history.

The [help center](/help/search-for-messages#search-by-message-id) also
documents the `near` operator for searching for messages by ID, but
this narrow operator has no effect on filtering messages when sent to
the server. In practice, when the `near` operator is used to search for
messages, or is part of a URL fragment, the value of its operand should
instead be used for the value of the `anchor` parameter in endpoints
that also accept a `narrow` parameter; see
[GET /messages][anchor-get-messages] and
[POST /messages/flags/narrow][anchor-post-flags].

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

### Channel and user IDs

There are a few additional narrow/search options (new in Zulip 2.1)
that use either channel IDs or user IDs that are not documented in the
help center because they are primarily useful to API clients:

* `channel:1234`: Search messages sent to the channel with ID `1234`.
* `sender:1234`: Search messages sent by user ID `1234`.
* `dm:1234`: Search the direct message conversation between
  you and user ID `1234`.
* `dm:1234,5678`: Search the direct message conversation between
  you, user ID `1234`, and user ID `5678`.
* `dm-including:1234`: Search all direct messages (1-on-1 and group)
  that include you and user ID `1234`.

!!! tip ""

    A user ID can be found by [viewing a user's profile][view-profile]
    in the web or desktop apps. A channel ID can be found when [browsing
    channels][browse-channels] in the web or desktop apps.

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
[browse-channels]: /help/introduction-to-channels#browse-and-subscribe-to-channels
[anchor-get-messages]: /api/get-messages#parameter-anchor
[anchor-post-flags]: /api/update-message-flags-for-narrow#parameter-anchor
