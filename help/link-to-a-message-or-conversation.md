# Link to a message or conversation

Zulip makes it easy to share links to messages, topics, and channels. You can
link from one Zulip [conversation](/help/reading-conversations) to another, or
share links to Zulip conversations in issue trackers, emails, or other external
tools.

## Link to a channel within Zulip

Channel links are automatically formatted as [#channel name]().

{start_tabs}

{!start-composing.md!}

1. Type `#` followed by a few letters from the channel name.

1. Pick the desired channel from the autocomplete.

1. Pick the top option from the autocomplete to link to the channel without
   selecting a topic.

!!! tip ""

    You can create a channel link manually by typing `#**channel name**`.

{end_tabs}

When you paste a channel link into Zulip, it's automatically formatted as
`#**channel name**`. You can paste as plain text if you prefer with <kbd
data-mac-following-key="⌥">Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>V</kbd>.

## Link to a topic within Zulip

Topic links are automatically formatted as [#channel > topic]().

{start_tabs}

{!start-composing.md!}

1. Type `#` followed by a few letters from the channel name.

1. Pick the desired channel from the autocomplete.

1. Type a few letters from the topic name.

1. Pick the desired topic from the autocomplete.

!!! tip ""

    You can create a topic link manually by typing `#**channel name>topic name**`.

{end_tabs}

When you paste a topic link into Zulip, it's automatically formatted as
`#**channel name>topic name**`. You can paste as plain text if you prefer with
<kbd data-mac-following-key="⌥">Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>V</kbd>.

## Link to Zulip from anywhere

All URLs in Zulip are designed to be shareable.  Copying the URL from
the browser's address bar will work for all views, including searches.

### Get a link to a specific message

This copies to your clipboard a permanent link to the message,
displayed in its thread (i.e. topic view for messages in a channel).
Viewing a topic via a message link will never mark messages as read.

These links will still work even when the message is [moved to another
topic](/help/move-content-to-another-topic) or
[channel](/help/move-content-to-another-channel), or if its [topic is
resolved](/help/resolve-a-topic). Zulip uses the same permanent link syntax when
[quoting a message](/help/quote-or-forward-a-message).

When you paste a message link into the compose box, it gets automatically
formatted to be easy to read:

```
#**channel name>topic name@message ID**
```

When you send your message, the link will appear as **#channel name>topic
name@💬**.

{start_tabs}

{tab|desktop-web}

{!message-actions-menu.md!}

1. Click **Copy link to message**.

!!! tip ""

    If using Zulip in a browser, you can also click on the timestamp
    of a message, and copy the URL from your browser's address bar.

!!! tip ""

    When you paste a message link into Zulip, it is automatically
    formatted for you. You can paste as plain text if you prefer with
    <kbd data-mac-following-key="⌥">Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>V</kbd>.

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

{!channel-actions.md!}

1. Click **Copy link to channel**.

{tab|mobile}

{!channel-long-press-menu.md!}

1. Tap **Copy link to channel**.

{!channel-long-press-menu-tip.md!}

{end_tabs}

## Related articles

* [Add a custom linkifier](/help/add-a-custom-linkifier)
* [Message formatting](/help/format-your-message-using-markdown)
* [Linking to your organization](/help/linking-to-zulip)
