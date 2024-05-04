# Configure automated notices

The Zulip sends automated notices via **Notification Bot** to notify users about
changes in their organization or account. Some types of notices can be
configured, or disabled altogether.

Notices sent to channels are translated into the language that the organization
has configured as the [language for automated messages and invitation
emails](/help/configure-organization-language). The topic name is also
translated. Notices sent directly to users will use [their preferred
language](/help/change-your-language).

## Notices about channels

Notices about channel settings changes, such as [name](/help/rename-a-channel),
[description](/help/change-the-channel-description),
[permission](/help/channel-permissions) and
[policy](/help/channel-posting-policy) updates are sent to the
“channel events” topic in the channel that was modified.

### New channel announcements

{!admin-only.md!}

When creating a new [public channel](/help/channel-permissions), the
channel creator can choose to advertise the new channel via an automated
notice. You can configure what channel Zulip uses for these notices, or
disable these notices entirely. The topic for these messages is “new
channels”.

New [private](/help/channel-permissions) channels are never announced.

{start_tabs}

{settings_tab|organization-settings}

1. Under **Automated messages and emails**, configure **New channel
   announcements**.

{!save-changes.md!}

{end_tabs}

## Notices about topics

A notice is sent when a topic is [resolved or
unresolved](/help/resolve-a-topic). These notices will be marked as unread only
for users who had participated in the topic.

Additionally, when moving messages to another
[channel](/help/move-content-to-another-channel) or
[topic](/help/move-content-to-another-topic), users can decide whether to send
automated notices to help others understand how content was moved.

## Notices about users

You will be notified if someone [subscribes you to a
channel](/help/add-or-remove-users-from-a-channel#add-users-to-a-channel), or
changes your [group](/help/user-groups) membership.

### New user announcements

{!admin-only.md!}

You can configure where **Notification Bot** will post an announcement when new
users join your organization, or disable new user announcement messages
entirely. The topic for these messages is “signups”.

{start_tabs}

{settings_tab|organization-settings}

1. Under **Automated messages and emails**, configure **New user
   announcements**.

{!save-changes.md!}

{end_tabs}

## Zulip update announcements

Zulip announces new features and other important product changes via automated
messages. This is designed to help users discover new features they may find
useful, including new configuration options.

These announcements are posted to the “Zulip updates” topic in the channel selected by
organization administrators. You can read update messages whenever it's
convenient, or [mute](/help/mute-a-topic) the topic if you are not interested.
If you organization does not want to receive these announcements, they can be
disabled.

On self-hosted Zulip servers, announcement messages are shipped with the Zulip
server version that includes the new feature or product change. You may thus
receive several announcement messages when your server is upgraded.

Unlike other notices, Zulip update announcements are not translated.

### Configure Zulip update announcements

{!admin-only.md!}

{start_tabs}

{settings_tab|organization-settings}

1. Under **Automated messages and emails**, configure **Zulip update
   announcements**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Organization language for automated messages and invitation emails](/help/configure-organization-language)
* [Moderating open organizations](/help/moderating-open-organizations)
* [Zulip newsletter](https://zulip.com/help/email-notifications#low-traffic-newsletter)
