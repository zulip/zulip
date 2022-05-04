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

## Link to Zulip from anywhere

All URLs in Zulip are designed to be shareable.
Copying the URL from the browser's address bar will work
for all views, including searches.
### Get a link to a specific message

This copies to your clipboard a permanent link to the message,
displayed in its thread (i.e. topic view for messages in a stream).
Viewing a topic via a message link will never mark messages as read.

These links will still work even when the message is
[moved to another topic](/help/move-content-to-another-topic)
or [stream](/help/move-content-to-another-stream) or
if its [topic is resolved](/help/resolve-a-topic).

Zulip uses the same permanent link syntax when [quoting a
message](/help/quote-and-reply).

{start_tabs}

{tab|desktop}

{!message-actions-menu.md!}

1. Click **Copy link to message**.

{tab|via-browser-address-bar}

1. Click on the timestamp of the message.

1. Copy the URL from your browser's address bar.

{end_tabs}

### Get a link to a specific topic:

{start_tabs}

{tab|desktop}

{!topic-actions.md!}

1. Click **Copy link to topic**.

{tab|via-browser-address-bar}

1. Click on a topic in the left sidebar.

1. Copy the URL from your browser's address bar.

{end_tabs}
### Get a link to a specific stream:

{start_tabs}

{tab|desktop}

1. Right-click on the stream in the left sidebar.

1. Click **Copy Link**.

{tab|via-browser-address-bar}

1. Click on a stream in the left sidebar.

1. Copy the URL from your browser's address bar.

{end_tabs}

## Related articles

* [Add a custom linkifier](/help/add-a-custom-linkifier)
* [Format your messages using Markdown](/help/format-your-message-using-markdown)
* [Linking to Zulip](/help/linking-to-zulip)
