# Edit or delete a message

Zulip makes it possible to edit the content of your messages, letting you fix
typos, clarify your thoughts, etc. You can also delete your messages if this is
allowed in your organization.

Organization administrators can
[configure](/help/restrict-message-editing-and-deletion) who can edit and delete
messages, and set time limits for these actions. Administrators can delete other
users' messages, but can never edit the content.

!!! tip ""

    You can also [edit message topics](/help/rename-a-topic).

## Edit a message

{start_tabs}

{tab|desktop-web}

{!message-actions.md!}

1. Click the **pencil** (<i class="fa fa-pencil"></i>) icon.  If you do not see
   the **pencil** (<i class="fa fa-pencil"></i>) icon, you do not have
   permission to edit this message.

1. Edit the content of the message.

1. Click **Save**.

{tab|mobile}

{!message-long-press-menu.md!}

1. Tap **Edit message**.  If you do not see the **Edit message** option, you do
   not have permission to edit this message.

1. Edit the content of the message.

1. Approve by tapping the **checkmark**
   (<img src="/static/images/help/mobile-check-circle-icon.svg" alt="checkmark" class="mobile-icon"/>)
   button in the bottom right corner of the app.

{end_tabs}

!!! tip ""

    After you have edited a message, the message is publicly
    marked as **EDITED**. You can
    [view a message's edit history](/help/view-a-messages-edit-history)
    if it is [enabled](/help/disable-message-edit-history) in your organization.

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

1. Click the **pencil** (<i class="fa fa-pencil"></i>) icon. If you do not see
   the **pencil** (<i class="fa fa-pencil"></i>) icon, you do not have
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

## Restoring deleted messages

For protection against accidental or immediately regretted
deletions, messages deleted directly or via a [message retention
policy](/help/message-retention-policy) are archived for 30 days in a
format that can be restored by a server administrator.  After that
time, they are permanently and irrecoverably deleted from the Zulip
server.  Server administrators can adjust the archival time using
the `ARCHIVED_DATA_VACUUMING_DELAY_DAYS` setting.

## Related articles

* [View the Markdown source of a message](/help/view-the-markdown-source-of-a-message)
* [Delete a topic](/help/delete-a-topic)
* [Archive a stream](/help/archive-a-stream)
* [Message retention policy](/help/message-retention-policy)
* [Restrict message editing and deletion](/help/restrict-message-editing-and-deletion)
