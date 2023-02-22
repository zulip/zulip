# Notifications in Zulip

This is a design document aiming to provide context for developers
working on Zulip's email notifications and mobile push notifications
code paths. We recommend first becoming familiar with [sending
messages](sending-messages.md); this document expands on
the details of the email/mobile push notifications code path.

## Important corner cases

Here we name a few corner cases worth understanding in designing this
sort of notifications system:

- The **idle desktop problem**: We don't want the presence of a
  desktop computer at the office to eat all notifications because the
  user has an "online" client that they may not have used in 3 days.
- The **hard disconnect problem**: A client can lose its connection to
  the Internet (or be suspended, or whatever) at any time, and this
  happens routinely. We want to ensure that races where a user closes
  their laptop shortly after a notifiable message is sent does not
  result in the user never receiving a notification about a message
  (due to the system thinking that client received it).

## The mobile/email notifications flow

As a reminder, the relevant part of the flow for sending messages is
as follows:

- `do_send_messages` is the synchronous message-sending code path,
  and passing the following data in its `send_event` call:
  - Data about the message's content (E.g. mentions, wildcard
    mentions, and alert words) and encodes it into the `UserMessage`
    table's `flags` structure, which is in turn passed into
    `send_event` for each user receiving the message.
  - Data about user configuration relevant to the message, such as
    `online_push_user_ids` and `stream_notify_user_ids`, are included
    in the main event dictionary.
  - The `presence_idle_user_ids` set, containing the subset of
    recipient users who can potentially receive notifications, but have not
    interacted with a Zulip client in the last few minutes. (Users who
    have generally will not receive a notification unless the
    `enable_online_push_notifications` flag is enabled). This data
    structure ignores users for whom the message is not notifiable,
    which is important to avoid this being thousands of `user_ids` for
    messages to large streams with few currently active users.
- The Tornado [event queue system](events-system.md)
  processes that data, as well as data about each user's active event
  queues, to (1) push an event to each queue needing that message and
  (2) for notifiable messages, pushing an event onto the
  `missedmessage_mobile_notifications` and/or `missedmessage_emails`
  queues. This important message-processing logic has notable extra
  logic not present when processing normal events, both for details
  like splicing `flags` to customize event payloads per-user, as well.
  - The Tornado system determines whether the user is "offline/idle".
    Zulip's email notifications are designed to not fire when the user
    is actively using Zulip to avoid spam, and this is where those
    checks are implemented.
  - Users in `presence_idle_user_ids` are always considered idle:
    the variable name means "users who are idle because of
    presence". This is how we solve the idle desktop problem; users
    with an idle desktop are treated the same as users who aren't
    logged in for this check.
  - However, that check does not handle the hard disconnect problem:
    if a user was present 1 minute before a message was sent, and then
    closed their laptop, the user will not be in
    `presence_idle_user_ids` (because it takes a
    [few minutes](presence.md) of being idle for Zulip
    clients to declare to the server that the user is actually idle),
    and so without an additional mechanism, messages sent shortly after
    a user leaves would never trigger a notification (!).
  - We solve that problem by also notifying if
    `receiver_is_off_zulip` returns `True`, which checks whether the user has any
    current events system clients registered to receive `message`
    events. This check is done immediately (handling soft disconnects,
    where E.g. the user closes their last Zulip tab and we get the
    `DELETE /events/{queue_id}` request).
  - The `receiver_is_off_zulip` check is effectively repeated when
    event queues are garbage-collected (in `missedmessage_hook`) by
    looking for whether the queue being garbage-collected was the only
    one; this second check solves the hard disconnect problem, resulting in
    notifications for these hard-disconnect cases usually coming 10
    minutes late.
  - We try to contain the "when to notify" business logic in the
    `zerver/lib/notification_data.py` class methods. The module has
    unit tests for all possible situations in
    `test_notification_data.py`.
  - The message-edit code path has parallel logic in
    `maybe_enqueue_notifications_for_message_update` for triggering
    notifications in cases like a mention added during message
    editing.
  - The notification sending logic for message edits
    inside Tornado has extensive automated test suites; e.g.
    `test_message_edit_notifications.py` covers all the cases around
    editing a message to add/remove a mention.
  - We may in the future want to add some sort of system for letting
    users see past notifications, to help with explaining and
    debugging this system, since it has so much complexity.
- Desktop notifications are the simplest; they are implemented
  client-side by the web/desktop app's logic
  (`web/src/notifications.js`) inspecting the `flags` fields that
  were spliced into `message` events by the Tornado system, as well as
  the user's notification settings.
- The queue processors for those queues make the final determination
  for whether to send a notification, and do the work to generate an
  email (`zerver/lib/email_notifications.py`) or mobile
  (`zerver/lib/push_notifications.py`) notification. We'll detail
  this process in more detail for each system below, but it's
  important to know that it's normal for a message to sit in these
  queues for minutes (and in the future, possibly hours).
- Both queue processor code paths do additional filtering before
  sending a notification:
  - Messages that have already been marked as read by the user before
    the queue processor runs never trigger a notification.
  - Messages that were already deleted never trigger a notification.
  - The user-level settings for whether email/mobile notifications are
    disabled are rechecked, as the user may have disabled one of these
    settings during the queuing period.
  - The **Email notifications queue processor**, `MissedMessageWorker`,
    takes care to wait for 2 minutes (hopefully in the future this will be a
    configuration setting) and starts a thread to batch together multiple
    messages into a single email. These features are unnecessary
    for mobile push notifications, because we can live-update those
    details with a future notification, whereas emails cannot be readily
    updated once sent. Zulip's email notifications are styled similarly
    to GitHub's email notifications, with a clean, simple design that
    makes replying from an email client possible (using the [incoming
    email integration](../production/email-gateway.md)).
  - The **Push notifications queue processor**,
    `PushNotificationsWorker`, is a simple wrapper around the
    `push_notifications.py` code that actually sends the
    notification. This logic is somewhat complicated by having to track
    the number of unread push notifications to display on the mobile
    apps' badges, as well as using the [mobile push notifications
    service](../production/mobile-push-notifications.md) for self-hosted
    systems.

The following important constraints are worth understanding about the
structure of the system, when thinking about changes to it:

- **Bulk database queries** are much more efficient for checking
  details from the database like "which users receiving this message
  are online".
- **Thousands of users**. Zulip supports thousands of users, and we
  want to avoid `send_event()` pushing large amounts of per-user data
  to Tornado via RabbitMQ for scalability reasons.
- **Tornado doesn't do database queries**. Because the Tornado system
  is an asynchronous event-driven framework, and our Django database
  library is synchronous, database queries are very expensive. So
  these queries need to be done in either `do_send_messages` or the
  queue processor logic. (For example, this means `presence` data
  should be checked in either `do_send_messages` or the queue
  processors, not in Tornado).
- **Future configuration**. Notification settings are an area that we
  expect to only expand with time, with upcoming features like
  following a topic (to get notifications for messages only within
  that topic in a stream). There are a lot of different workflows
  possible with Zulip's threading, and it's important to make it easy
  for users to set up Zulip's notification to fit as many of those
  workflows as possible.
- **Message editing**. Zulip supports editing messages, and that
  interacts with notifications in ways that require careful handling:
  Notifications should have
  the latest edited content (users often fix typos 30 seconds after
  sending a message), adding a mention when editing a message should
  send a notification to the newly mentioned user(s), and deleting a
  message should cancel any unsent notifications for it.
