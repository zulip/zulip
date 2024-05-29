# DMs, mentions, and alerts

You can configure desktop, mobile, and email notifications for
[direct messages (DMs)](/help/direct-messages),
[mentions](/help/mention-a-user-or-group), and [alert
words](#alert-words).

## Configure notifications

These settings will affect notifications for direct messages, group
direct messages, mentions, and alert words.

{start_tabs}

{settings_tab|notifications}

1. In the **Notification triggers** table, toggle the settings for **DMs, mentions, and alerts**.

{end_tabs}

You can also hide the content of direct messages (and group direct
messages) from desktop notifications.

{start_tabs}

1. Under **Desktop message notifications**, toggle
**Include content of direct messages in desktop notifications**.

{end_tabs}

## Wildcard mentions

By default, wildcard mentions (`@**all**`, `@**everyone**`, `@**channel**`,
or `@**topic**`) trigger email/push notifications as though they were
personal @-mentions. You can toggle whether you receive notifications
for wildcard mentions.

!!! tip ""

    Unlike personal mentions, wildcard mentions do not trigger notifications
    in muted channels or topics.

{start_tabs}

{settings_tab|notifications}

1.  In the **Notification triggers** table, toggle the **@all** checkbox for
    **Channels** or **Followed topics**.

{end_tabs}

Additionally, you can override this configuration for individual
channels in your [Channel settings](/help/channel-notifications), and
administrators can [restrict use of wildcard
mentions](/help/restrict-wildcard-mentions) in large channels.

## Alert words

Zulip lets you to specify **alert words or phrases** that send you a desktop
notification whenever the alert word is included in a message. Alert words are
case-insensitive.

!!! tip ""

    Alert words in messages you receive while the alert is enabled will be highlighted.

### Add an alert word or phrase

{start_tabs}

{settings_tab|alert-words}

1. Add a word or phrase.

1. Click **Add alert word**.

{end_tabs}

## Related articles

* [Desktop notifications](/help/desktop-notifications)
* [Email notifications](/help/email-notifications)
* [Mobile notifications](/help/mobile-notifications)
* [Restrict wildcard mentions](/help/restrict-wildcard-mentions)
* [Channel notifications](/help/channel-notifications)
* [View your mentions](/help/view-your-mentions)
* [Do not disturb](/help/do-not-disturb)
