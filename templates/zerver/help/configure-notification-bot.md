# Notification bot

The Zulip notification bot automatically generates messages for
various organization level events, including:

* Stream settings changes such as [name](/help/rename-a-stream),
  [description](/help/change-the-stream-description),
  [permission](/help/stream-permissions) and
  [policy](/help/stream-sending-policy) updates (sent to the
  "stream events" topic)
* A topic being [resolved/unresolved](/help/resolve-a-topic)
* New public stream announcements (private streams are not announced)
* New user announcements

The notification bot also generates messages to individual users
for some user specific events, such as [being subscribed to a
stream][add-users-to-stream] by another user.

Organization administrators can configure where (and whether)
[new stream](#new-stream-notifications) and
[new user](#new-user-notifications) announcement messages are sent.

Stream messages sent by the notification bot (including the topic)
are translated into the language that the organization has configured
as the [organization notifications language][org-notifications-lang].
Notification bot messages sent to a single user will use
[their preferred language](/help/change-your-language).

## Configure notification bot

{!admin-only.md!}

### New stream notifications

You can configure where the Zulip notification bot
[announces][new-stream-options] new public streams, or disable the new
stream notification messages entirely. The topic for these messages
is "new streams".

{start_tabs}

{settings_tab|organization-settings}

1. Under **Notifications**, configure **New stream notifications**.

{!save-changes.md!}

{end_tabs}

### New user notifications

You can configure where the Zulip notification bot announces new users,
or disable the new user notification messages entirely. The topic for
these messages is "signups".

{start_tabs}

{settings_tab|organization-settings}

1. Under **Notifications**, configure **New user notifications**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Organization notifications language][org-notifications-lang]
* [Streams and topics](/help/streams-and-topics)

[add-users-to-stream]: /help/add-or-remove-users-from-a-stream#add-users-to-a-stream
[api-create-user]: https://zulip.com/api/create-user
[new-stream-options]: /help/create-a-stream#stream-options
[org-notifications-lang]: /help/change-the-default-language-for-your-organization
