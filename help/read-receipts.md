# Read receipts

Read receipts let you check who has read a message. You can see read receipts
for any message, including both [channel messages](/help/introduction-to-channels)
and [direct messages](/help/direct-messages).

With privacy in mind, Zulip lets you [control][configure-personal-read-receipts]
whether your read receipts are shared, and administrators can
[choose][configure-organization-read-receipts] whether to enable read receipts in
their organization.

!!! tip ""
    Read receipts reflect whether or not someone has marked a message as read,
    whether by viewing it, or [by marking messages as read in
    bulk](/help/marking-messages-as-read).

## View who has read a message

{start_tabs}

{tab|desktop-web}

{!message-actions-menu.md!}

1. Click **View read receipts**.

!!! keyboard_tip ""

    You can also use <kbd>Shift</kbd> + <kbd>V</kbd> to show or hide read receipts
    for the selected message.

{tab|mobile}

Access this feature by following the web app instructions in your
mobile device browser.

Implementation of this feature in the mobile app is tracked [on
GitHub](https://github.com/zulip/zulip-flutter/issues/667). If
you're interested in this feature, please react to the issue's
description with 👍.

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
  that users [can always change this setting][configure-personal-read-receipts]
  once they join.)

### Configure whether read receipts are enabled in your organization

{start_tabs}

{settings_tab|organization-settings}

1. Under **Message feed settings**, toggle **Enable read receipts**.

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

[configure-personal-read-receipts]: /help/read-receipts#configure-whether-zulip-lets-others-see-when-youve-read-messages
[configure-organization-read-receipts]:
    /help/read-receipts#configure-whether-read-receipts-are-enabled-in-your-organization
