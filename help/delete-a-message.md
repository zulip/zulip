# Delete a message

Zulip lets you delete the content of your messages or delete messages completely
if these actions are allowed in your organization. Only server administrators
can restore deleted messages.

Organization administrators can
[configure](/help/restrict-message-editing-and-deletion) who can edit and delete
messages, and set time limits for these actions. Administrators can delete other
users' messages completely, but cannot edit a message to delete its content.

## Delete message content

Editing a message to delete its content will cause the message to be displayed
as **(deleted)**.  The original sender and timestamp of the message will still
be displayed, and the original content of the message is still accessible via
Zulip's [edit history](/help/view-a-messages-edit-history) feature.  This can be
the best option for avoiding confusion if other users have already responded to
your message.

{start_tabs}

{tab|desktop-web}

{!message-actions.md!}

1. Click the **pencil** (<i class="zulip-icon zulip-icon-edit"></i>) icon. If you do not see
   the **pencil** (<i class="zulip-icon zulip-icon-edit"></i>) icon, you do not have
   permission to delete the content of this message.

1. Delete the content of the message.

1. Click **Save**.

{tab|mobile}

{!message-long-press-menu.md!}

1. Tap **Delete message** to delete the content of the message.  If you do not
   see the **Delete message** option, you do not have permission to delete the
   content of this message.

{end_tabs}

## Delete a message completely

In some cases, such as when a message accidentally shares secret information, or
contains spam or abuse, it makes sense to delete a message completely. Deleted
messages will immediately disappear from the UI in all official Zulip clients.

Any uploaded files referenced only by deleted messages will be immediately
inaccessible. Note that an uploaded file shared in multiple messages will be
deleted only when *all* of those messages are deleted.

It's important to understand that anyone who received the message
before you deleted it could have made a copy of its content. Even if
no one is online when you send the message, users may have received
the message via email or mobile notifications. So if you
accidentally shared secret information that you can change, like a
password, you may want to change that password regardless of whether
you also delete the message.

{start_tabs}

{tab|desktop-web}

{!message-actions-menu.md!}

1. Select **Delete message**. If you do not see the **Delete message** option,
   you do not have permission to delete this message completely.

2. Approve by clicking **Confirm**.

{end_tabs}

!!! tip ""

    You can delete messages sent by [bots that you
    own](/help/view-your-bots) just like messages you sent yourself.

## Restoring deleted messages

For protection against accidental or immediately regretted
deletions, messages deleted directly or via a [message retention
policy](/help/message-retention-policy) are archived for 30 days in a
format that can be restored by a server administrator.  After that
time, they are permanently and irrecoverably deleted from the Zulip
server.  Server administrators can adjust the archival time using
the `ARCHIVED_DATA_VACUUMING_DELAY_DAYS` setting.

## Message notifications

If you delete a message soon after sending it, any [pending email
notifications](/help/email-notifications#delay-before-sending-emails)
for that message will be canceled, and
[visual desktop notifications](/help/desktop-notifications) will be removed,
including [mentions and alerts](/help/dm-mention-alert-notifications).

## Related articles

* [Delete a topic](/help/delete-a-topic)
* [Archive a channel](/help/archive-a-channel)
* [Message retention policy](/help/message-retention-policy)
* [Edit a message](/help/edit-a-message)
* [Restrict message editing and deletion](/help/restrict-message-editing-and-deletion)
