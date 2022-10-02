# Move content to another stream

Zulip makes it possible to move messages, or an entire topic, to another
stream. Organizations can [configure][move-permission-setting] which
[roles](/help/roles-and-permissions) have permission to move messages
between streams.

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

1. Select **Move topic**.

1. Select the destination stream for the topic from the streams dropdown list.

1. (optional) Change the topic.

1. Toggle whether automated notices should be sent.

1. Click **Confirm**.


!!! warn ""

    **Note**: When a topic is moved to a private stream with protected history,
              messages in the topic will be visible to all the subscribers.


{end_tabs}

## Move messages to another stream

{start_tabs}

{!message-actions-menu.md!}

1. Select the first option. It may be called **View source / Move message**,
   or simply **Edit message**. If it's called **View source**, then you are not
   allowed to edit the stream of that message.

1. Select the destination stream for the message from the streams dropdown list.

1. (optional) Change the topic.

1. Toggle whether automated notices should be sent.

1. From the dropdown menu, select which messages to move.

1. Click **Save**.


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
* [Configure message editing and deletion](/help/configure-message-editing-and-deletion)

[move-permission-setting]: /help/configure-message-editing-and-deletion#configure-who-can-move-topics-between-streams
[notification-bot]: /help/configure-notification-bot
