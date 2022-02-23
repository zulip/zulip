# Move content to another stream

Organization administrators can move topics from one
stream to another, or move a subset of messages to a topic from one
stream to another.

Organization administrators can
[configure who can edit topics](/help/configure-who-can-edit-topics), or turn off
message editing entirely. See the
[guide to message and topic editing](/help/configure-message-editing-and-deletion)
for the details on when topic editing is allowed.

## Move a topic to another stream

Organizations can configure which roles have permission to [move
topics between streams][move-permission-setting].

To move a topic, you must have access to both the source and
destination streams.

{start_tabs}

{!topic-actions.md!}

1. Select **Move topic**.

1. Select the destination stream for the topic from the streams dropdown list.

1. (Optional) Change the topic.

1. Select whether you want automated notification messages to be sent
   to the old location for the topic, new location for the topic, or both.

1. Click **Move topic**.


!!! warn ""

    **Note**: When a topic is moved to a private stream with protected history,
              messages in the topic will be visible to all the subscribers.


{end_tabs}

## Move message(s) in a topic to another stream

Organizations can configure which roles have permission to [move
topics between streams][move-permission-setting].

Roles that have permission can also move only a subset of messages
from a topic to another stream.

{start_tabs}

{!message-actions-menu.md!}

1. Select the first option. It may be called **View source / Move message**,
   or simply **Edit**. If it's called **View source**, then you are not
   allowed to edit the stream of that message.

1. Select the destination stream for the message from the streams dropdown list.

1. (Optional) Change the topic.

1. A dropdown with three options will appear to the right:
**Change only this message topic**, **Change later messages to this topic**, and
**Change previous and following messages to this topic**. Pick the appropriate
option.

1. Select whether you want automated notification messages to be sent
   to the old location for the topic, new location for the topic, or both.

1. Click **Save**.


!!! warn ""

    **Note**: You cannot edit content of a message while changing its stream.

{end_tabs}

## Related articles

* [Rename a topic](/help/rename-a-topic)
* [Move content to another topic](/help/move-content-to-another-topic)

[move-permission-setting]: /help/configure-message-editing-and-deletion#configure-who-can-move-topics-between-streams
