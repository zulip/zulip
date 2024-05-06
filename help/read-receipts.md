# Read receipts

Read receipts let you check who has read a message. You can see read receipts
for any message, including both [channel messages](/help/introduction-to-channels)
and [direct messages](/help/direct-messages).

With privacy in mind, Zulip lets you [control][configure-personal-read-recipts]
whether your read receipts are shared, and administrators can
[choose][configure-organization-read-recipts] whether to enable read receipts in
their organization.

!!! tip ""
    Read receipts reflect whether or not someone has marked a message as read,
    whether by viewing it, or [by marking messages as read in
    bulk](/help/marking-messages-as-read).

## View who has read a message

{start_tabs}

{tab|desktop-web}

{!message-actions-menu.md!}

3. Click **View read receipts**.

{tab|mobile}

{!message-long-press-menu.md!}

1. Tap **View read receipts**.

{end_tabs}

!!! tip ""
    In addition to a list of names, you will see how many people have read
    the message.

## Configure whether Zulip lets others see when you've read messages

Zulip supports the privacy option of never sharing whether or not you have read
a message. If this setting is turned off, your name will never appear in the
list of read receipts.

{start_tabs}

{settings_tab|account-and-privacy}

1. Under **Privacy**, toggle **Let others see when I've read messages**.

{end_tabs}

## Configure read receipts for your organization

{!admin-only.md!}

You can configure:

* Whether read receipts are enabled in your organization.
* Whether new users will allow others to view read receipts by default. (Note
  that users [can always change this setting][configure-personal-read-recipts]
  once they join.)

### Configure whether read receipts are enabled in your organization

{start_tabs}

{settings_tab|organization-settings}

1. Under **Other settings**, toggle **Enable read receipts**.

{!save-changes.md!}

{end_tabs}

### Configure default read receipt sharing settings for new users

{start_tabs}

{settings_tab|default-user-settings}

1. Under **Privacy settings**, toggle **Allow other users to view read receipts**.

{end_tabs}

## Related articles

* [Status and availability](/help/status-and-availability)
* [Typing notifications](/help/typing-notifications)
* [Marking messages as read](/help/marking-messages-as-read)
* [Marking messages as unread](/help/marking-messages-as-unread)

[configure-personal-read-recipts]: /help/read-receipts#configure-whether-zulip-lets-others-see-when-youve-read-messages
[configure-organization-read-recipts]:
    /help/read-receipts#configure-whether-read-receipts-are-enabled-in-your-organization
