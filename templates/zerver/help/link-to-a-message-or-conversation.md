# Link to a message or conversation

Zulip makes it easy to share links to messages, topics, and streams. You can
link from one Zulip conversation to another, or share links to Zulip conversations
in issue trackers, emails, or other external tools.

## Link to a stream or topic within Zulip

Zulip automatically creates links to streams and topics in messages you send.

The easiest way to link to a stream or topic is:

{start_tabs}

1. Type `#` followed by the one or more letters of the stream name.

2. Choose the desired stream from the auto-complete menu. The link will be
   automatically formatted for you.

3. If linking to a topic, type `>` after selecting a stream as described above,
   followed by one or more letters of the topic name.

4. Choose the desired topic from the auto-complete menu. The link will be
   automatically formatted for you.

{end_tabs}

Alternatively, it is possible to manually format stream and topic links:

```
Stream: #**stream name**
Topic: #**stream name>topic name**
```

## Link to a stream or topic from anywhere

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
* [Linking to Zulip](/help/linking-to-zulip)
