# Edit or delete a message

!!! warn ""
    **Note:** Editing message topic is discussed in a
    [separate guide](/help/change-the-topic-of-a-message).

By default, Zulip allows you to edit the content of your messages within 10
minutes of when you send them. Organization administrators can
[change the time limit](/help/configure-message-editing-and-deletion),
remove the time limit, or remove the ability to edit messages entirely.

Administrators can delete other users' messages, but can never edit the
content.

## Edit a message

{start_tabs}

{!message-actions.md!}

1. Click the pencil (<i class="fa fa-pencil"></i>) icon.

1. Edit the message, and click **Save**.

{end_tabs}

!!! warn ""
    **Note:** After you have edited a message, the message is publicly marked as
    `(EDITED)`. You can [view](/help/view-a-messages-edit-history) a message's
    edit history, assuming that feature has not been
    [disabled by an organization administrator](/help/disable-message-edit-history).

If you don't see the pencil (<i class="fa fa-pencil"></i>) icon, the message content
can no longer be edited. You should see a file (<i class="fa fa-file-code-o"></i>)
icon instead. Clicking the file icon will allow you to view the
[Markdown source](/help/view-the-markdown-source-of-a-message) of the message, or
[edit the topic](/help/change-the-topic-of-a-message).

## Delete a message

Editing a message to delete its content will cause the message to be
displayed as `(deleted)`.  The original sender and timestamp of the
message will still be displayed, and the original content of the
message is still accessible via Zulip's [edit
history](/help/view-a-messages-edit-history) feature.  This can be the
least confusing option for other users.

### Delete a message completely

For cases where someone accidentally shared secret information publicly
(e.g. you posted an employee's salary), it can make sense to delete a
message completely.

By default, only administrators can delete messages, though this can be
[configured](/help/configure-message-editing-and-deletion) by an organization
administrator.

{start_tabs}

{!message-actions-menu.md!}

1. Select **Delete message**.

{end_tabs}

If you don't see the **Delete message** option, it means you don't have
permissions to delete that message.

## How deletion works

* Deleted messages will immediately disappear from the UI in all
  official Zulip clients.
* Any uploaded files referenced only by deleted messages will also be
  immediately inaccessible (An uploaded file shared in multiple
  messages will not be deleted until all of those messages are
  deleted).
* It's important to understand that anyone who received the message
  before you deleted it could have made a copy of its content. Even if
  no one is online when you send the message, users may have received
  the message via email or mobile notifications. So if you
  accidentally shared secret information that you can change, like a
  password, you may want to change that password regardless of whether
  you also delete the message.
* For protection against accidental or immediately regretted
  deletions, messages deleted directly or via a [message retention
  policy](/help/message-retention-policy) are archived for 7 days in a
  format that can be restored by a server administrator.  After that
  time, they are permanently and irrecoverably deleted from the Zulip
  server.  Server administrators can adjust the archival time using
  the `ARCHIVED_DATA_VACUUMING_DELAY_DAYS` setting.

## Related articles

* [Delete a topic](/help/delete-a-topic)
* [Delete a stream](/help/delete-a-stream)
* [Message retention policy](/help/message-retention-policy)
* [Configure editing and deletion policies](/help/configure-message-editing-and-deletion)
