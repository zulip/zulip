# Move content to another stream

Zulip makes it possible to move messages, or an entire topic, to another stream.
Organizations can [configure][configure-moving-permissions] which
[roles](/help/roles-and-permissions) have permission to move messages between
streams.

[configure-moving-permissions]: /help/restrict-moving-messages#configure-who-can-move-messages-to-another-stream

To help others find moved content, you can have the [notification
bot][notification-bot] send automated notices to the source topic, the
destination topic, or both. These notices include:

* A link to the source or destination topic.
* How many messages were moved, or whether the whole topic was moved.
* Who moved the content.

## Move a topic to another stream

To move a topic, you must have access to both the source and
destination streams.

{start_tabs}

{!topic-actions.md!}

1. Select **Move topic**. If you do not see this option, you do not have permission
   to move this topic.

1. Select the destination stream for the topic from the streams dropdown list.

1. _(optional)_ Change the topic name.

1. Toggle whether automated notices should be sent.

1. Click **Confirm** to move the topic to another stream.


!!! warn ""

    **Note**: When a topic is moved to a private stream with protected history,
              messages in the topic will be visible to all the subscribers.


{end_tabs}

## Move messages to another stream

{start_tabs}

{!message-actions-menu.md!}

1. Select **Move messages**. If you do not see this option, you do not have permission
   to move this message.

1. Select the destination stream from the streams dropdown list. If
   the stream input is disabled, you do not have permission to move
   this message to a different stream.

1. _(optional)_ Change the topic name.

1. From the dropdown menu, select which messages to move.

1. Toggle whether automated notices should be sent.

1. Click **Confirm** to move the selected content to another stream.


!!! warn ""

    **Note**: You cannot edit content of a message while changing its stream.

{end_tabs}

## Moving content to private streams

Access to messages moved to another stream will immediately be controlled by the
access policies for the destination stream. Content moved to a private stream will
thus appear to be deleted to users who are not subscribers of the destination stream.

Content moved to a [private stream with protected history](/help/stream-permissions)
will only be accessible to users who both:

* Were subscribed to the *original* stream when the content was *sent*.
* Are subscribed to the *destination* stream when the content is *moved*.

## Moving content out of private streams

In [private streams with protected history](/help/stream-permissions),
Zulip determines whether to treat the entire topic as moved using the
access permissions of the user requesting the topic move. This means
that the automated notices sent by the notification bot will report
that the entire topic was moved if the requesting user moved every
message in the topic that they can access, regardless of whether older
messages exist that they cannot access.

Similarly, [muted topics](/help/mute-a-topic) will be migrated to the
new stream and topic if the requesting user moved every message in the
topic that they can access.

This model ensures that the topic editing feature cannot be abused to
determine any information about the existence of messages or topics
that one does not have permission to access.

## Related articles

* [Rename a topic](/help/rename-a-topic)
* [Move content to another topic](/help/move-content-to-another-topic)
* [Restrict moving messages](/help/restrict-moving-messages)

[notification-bot]: /help/configure-notification-bot
