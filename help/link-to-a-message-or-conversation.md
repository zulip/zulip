# Link to a message or conversation

Zulip makes it easy to share links to messages, topics, and channels. You can
link from one Zulip [conversation](/help/reading-conversations) to another, or
share links to Zulip conversations in issue trackers, emails, or other external
tools.

## Link to a channel or topic within Zulip

Zulip automatically creates links to channels and topics in messages you send.

The easiest way to link to a channel or topic is:

{start_tabs}

1. Type `#` followed by the one or more letters of the channel name.

1. Choose the desired channel from the auto-complete menu. The link will be
   automatically formatted for you.

1. If linking to a topic, type `>` after selecting a channel as
   described above, followed by one or more letters of the topic name.

1. Choose the desired topic from the auto-complete menu. The link will be
   automatically formatted for you.

{end_tabs}

Alternatively, it is possible to manually format channel and topic links:

```
Channel: #**channel name**
Topic: #**channel name>topic name**
```

## Link to Zulip from anywhere

All URLs in Zulip are designed to be shareable.  Copying the URL from
the browser's address bar will work for all views, including searches.

### Get a link to a specific message

This copies to your clipboard a permanent link to the message,
displayed in its thread (i.e. topic view for messages in a channel).
Viewing a topic via a message link will never mark messages as read.

These links will still work even when the message is
[moved to another topic](/help/move-content-to-another-topic)
or [channel](/help/move-content-to-another-channel) or
if its [topic is resolved](/help/resolve-a-topic).

Zulip uses the same permanent link syntax when [quoting a
message](/help/quote-and-reply).

{start_tabs}

{tab|desktop-web}

{!message-actions-menu.md!}

1. Click **Copy link to message**.

!!! tip ""

    If using Zulip in a browser, you can also click on the timestamp
    of a message, and copy the URL from your browser's address bar.

{end_tabs}

### Get a link to a specific topic

{start_tabs}

{tab|desktop-web}

{!topic-actions.md!}

1. Click **Copy link to topic**.

!!! tip ""

    If using Zulip in a browser, you can also click on a topic name,
    and copy the URL from your browser's address bar.

{tab|mobile}

{!topic-long-press-menu.md!}

1. Tap **Copy link to topic**.

{!topic-long-press-menu-tip.md!}

{end_tabs}

### Get a link to a specific channel

{start_tabs}

{tab|desktop-web}

1. Right-click on a channel in the left sidebar.

1. Click **Copy Link**.

!!! tip ""

    If using Zulip in a browser, you can also click on a channel in the
    left sidebar, and copy the URL from your browser's address bar.

{tab|mobile}

{!channel-long-press-menu.md!}

1. Tap **Copy link to channel**.

{!channel-long-press-menu-tip.md!}

{end_tabs}

## Related articles

* [Add a custom linkifier](/help/add-a-custom-linkifier)
* [Message formatting](/help/format-your-message-using-markdown)
* [Linking to your organization](/help/linking-to-zulip)
