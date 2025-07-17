# Link to a message or conversation

Zulip makes it easy to share links to messages, topics, and channels. You can
link from one Zulip [conversation](/help/reading-conversations) to another, or
share links to Zulip conversations in issue trackers, emails, or other external
tools.

## Link to a channel within Zulip

Channel links are automatically formatted as [#channel name](#link-to-a-channel-within-zulip).

{start_tabs}

{!start-composing.md!}

1. Type `#` followed by a few letters from the channel name.

1. Pick the desired channel from the autocomplete.

1. Pick the top option from the autocomplete to link to the channel without
   selecting a topic.

!!! tip ""

    To link to the channel you're composing to, type `#>`, and pick the
    top option from the autocomplete.

{end_tabs}

When you paste a channel link into Zulip, it's automatically formatted as
`#**channel name**`. You can paste as plain text if you prefer with <kbd
data-mac-following-key="⌥">Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>V</kbd>.

You can create a channel link manually by typing `#**channel name**`

## Link to a topic within Zulip

Topic links are automatically formatted as [#channel > topic](#link-to-a-topic-within-zulip).

{start_tabs}

{!start-composing.md!}

1. Type `#` followed by a few letters from the channel name.

1. Pick the desired channel from the autocomplete.

1. Type a few letters from the topic name.

1. Pick the desired topic from the autocomplete.

!!! tip ""

    To link to a topic in the channel you're composing to, type `#>`
    followed by a few letters from the topic name, and pick the desired
    topic from the autocomplete.

{end_tabs}

When you paste a topic link into Zulip, it's automatically formatted as
`#**channel name>topic name**`. You can paste as plain text if you prefer with
<kbd data-mac-following-key="⌥">Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>V</kbd>.

You can create a topic link manually by typing `#**channel name>topic name**`.

## Link to Zulip from anywhere

All URLs in Zulip are designed to be **shareable**, including:

- Links to messages, topics, and channels.
- Search URLs, though note that personal
  [filters](/help/search-for-messages#search-filters) (e.g., `is:followed`) will
  be applied according to the user who's viewing the URL.

In addition, links to messages, topics, and channels are **permanent**:

- [Message links](#get-a-link-to-a-specific-message) will still work even when
  the message is [moved to another topic](/help/move-content-to-another-topic)
  or [channel](/help/move-content-to-another-channel), or if its [topic is
  resolved](/help/resolve-a-topic). Zulip uses the same permanent link syntax
  when [quoting a message](/help/quote-or-forward-a-message).

- [Topic links](#get-a-link-to-a-specific-topic) will still work even when the
  topic is [renamed](/help/rename-a-topic), [moved to another
  channel](/help/move-content-to-another-channel), or
  [resolved](/help/resolve-a-topic).

!!! tip ""

    When some messages are [moved out of a
    topic](/help/move-content-to-another-topic) and others are left in place,
    links to that topic will follow the location of the message whose ID is
    encoded in the topic URL (usually the first or last message in the topic).

- [Channel links](#get-a-link-to-a-specific-channel) will still work even when a
  channel is [renamed](/help/rename-a-channel) or
  [archived](/help/archive-a-channel).

When you copy a Zulip link and paste it anywhere that accepts HTML
formatting (e.g., your email, GitHub, docs, etc.), the link will be
formatted as it would be in Zulip (e.g., [#channel > topic](/)). To paste the
plain URL, you can paste without formatting (likely <kbd>Ctrl</kbd> +
<kbd>Shift</kbd> + <kbd>V</kbd> in your browser).

### Get a link to a specific message

This copies to your clipboard a permanent link to the message, displayed in the
context of its conversation. To preserve your reading status, messages won't be
automatically marked as read when you view a conversation via a message link.

When you paste a message link into the compose box, it gets automatically
formatted to be easy to read:

```
#**channel name>topic name@message ID**
```

When you send your message, the link will appear as [#channel > topic @ 💬](/).

{start_tabs}

{tab|desktop-web}

{!message-actions-menu.md!}

1. Click **Copy link to message**.

!!! tip ""

    If using Zulip in a browser, you can also click on the timestamp
    of a message, and copy the URL from your browser's address bar.

{end_tabs}

When you paste a message link into Zulip, it is automatically
formatted for you. You can paste as plain text if you prefer with
<kbd data-mac-following-key="⌥">Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>V</kbd>.

### Get a link to a specific topic

{start_tabs}

{tab|desktop-web}

{!topic-actions.md!}

1. Click **Copy link to topic**.

!!! tip ""

    If using Zulip in a browser, you can also click on a topic name,
    and copy the URL from your browser's address bar.

{tab|mobile}

Access this feature by following the web app instructions in your
mobile device browser.

Implementation of this feature in the mobile app is tracked [on
GitHub](https://github.com/zulip/zulip-flutter/issues/792). If
you're interested in this feature, please react to the issue's
description with 👍.

{end_tabs}

### Get a link to a specific channel

{start_tabs}

{tab|desktop-web}

{!channel-actions.md!}

1. Click **Copy link to channel**.

{tab|mobile}

Access this feature by following the web app instructions in your
mobile device browser.

Implementation of this feature in the mobile app is tracked [on
GitHub](https://github.com/zulip/zulip-flutter/issues/1227). If
you're interested in this feature, please react to the issue's
description with 👍.

{end_tabs}

## Related articles

* [Add a custom linkifier](/help/add-a-custom-linkifier)
* [Message formatting](/help/format-your-message-using-markdown)
* [Linking to your organization](/help/linking-to-zulip)
* [Pin information](/help/pin-information)
