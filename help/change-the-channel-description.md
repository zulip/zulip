# Change a channel's description

Channel descriptions can be used to explain the purpose of a channel, and link
to usage guidelines, resources, or related channels. They appear in the
navigation bar at the top of the web and desktop apps when you view the channel.
You can hover over long channel descriptions with the mouse to view them in
full.

Channel descriptions support Zulip's standard [Markdown
formatting][markdown-formatting], with the exception that image previews are
disabled. Use Markdown formatting to include a link to a website, Zulip
[message][message-link], or [topic][topic-link] in the channel description:
`[link text](URL)`.

{start_tabs}

{tab|desktop-web}

{relative|channel|all}

1. Select a channel.

{!select-channel-view-general.md!}

1. Click the **edit channel name and description**
   (<i class="zulip-icon zulip-icon-edit"></i>) icon to the right of the
   channel name, and enter a new description.

{!save-changes.md!}

{!channel-settings-general-tab-tip.md!}

{tab|mobile}

Access this feature by following the web app instructions in your
mobile device browser.

Implementation of this feature in the mobile app is tracked [on
GitHub](https://github.com/zulip/zulip-flutter/issues/1102). If
you're interested in this feature, please react to the issue's
description with 👍.

{end_tabs}

{!automated-notice-channel-event.md!}

## Related articles

* [Pin information](/help/pin-information)
* [View channel information](/help/view-channel-information)
* [Rename a channel](/help/rename-a-channel)
* [Markdown formatting][markdown-formatting]
* [Channel permissions](/help/channel-permissions)

[markdown-formatting]: /help/format-your-message-using-markdown
[message-link]: /help/link-to-a-message-or-conversation#get-a-link-to-a-specific-message
[topic-link]: /help/link-to-a-message-or-conversation#get-a-link-to-a-specific-topic
