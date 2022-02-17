# Link to a message or conversation

Share links to messages, topics, and streams. With Zulip,
it's easy to to link to specific (parts of) conversations from
issue trackers, documentation, or other external tools.

Also, when composing a message in Zulip, you can use
[Zulip's Markdown][zulip-markdown-links]
features to easliy auto-link to existing streams and topics.

[zulip-markdown-links]: /help/format-your-message-using-markdown#links

## Markdown syntax to auto-link to a stream or topic
```
Stream: #**stream name**
Topic: #**stream name>topic name**
```

!!! tip ""

    When using this Markdown feature in the compose box, a menu of
    valid streams should appear as you're typing. Once you've highlighted
    the desired stream name from the menu, you can press `>` for a list
    of valid topic names in that particular stream.

## Link to a stream or topic

{start_tabs}

1. Click on a stream or topic in the left sidebar.

1. Copy the URL from your browser's address bar.

{end_tabs}

!!! warn ""

    This works for all views, including searches.
    All URLs in Zulip are designed to be shareable.

## Link to a specific message

This will copy to your clipboard a permanent link to the message,
displayed in its thread (i.e. topic view for messages in a stream).
Viewing a topic via a message link will never mark messages as read.

Zulip uses the same permanent link syntax when [quoting a
message](/help/quote-and-reply).

{start_tabs}

{!message-actions-menu.md!}

1. Click **Copy link to message**.

{end_tabs}

## Related articles

* [Add a custom linkifier](/help/add-a-custom-linkifier)
* [Format your messages using Markdown](/help/format-your-message-using-markdown)
* [Link to your Zulip](/help/linking-to-zulip)
