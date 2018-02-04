# Edit or delete a message

!!! warn ""
    **Note:** Editing topic titles is discussed in a
    [separate guide](/help/change-the-topic-of-a-message). Additionally, Zulip
    messages cannot be deleted, but they can be edited so that their contents
    are blank.

Zulip allows you to easily edit the contents of your messages after they have
been posted.

{!message-actions.md!} pencil (<i class="icon-vector-pencil"></i>) icon
to reveal a message editing box.

2. After making the changes to your message in the message editing box, click
the **Save** button to save the changes you made to your message.

!!! warn ""
    **Note:** After you have edited a message, the message is publicly marked as
    `(EDITED)`. You can [view](/help/view-a-messages-edit-history) a message's
    edit history, assuming that feature has not been
    [disabled by an organization administrator](/help/disable-message-edit-history).

## Message editing time limit

Depending on your organization settings, Zulip may be configured with a time
limit within which you may edit a message (e.g. 10 minutes). As soon as that
limit has passed, the pencil (<i class="icon-vector-pencil"></i>) icon
changes to a file (<i class="icon-vector-file-text-alt"></i>) icon.

!!! tip ""
    Clicking on (<i class="icon-vector-file-text-alt"></i>) icon will allow you to
    view the [Markdown source](/help/view-the-markdown-source-of-a-message) or
    [change the topic](/help/change-the-topic-of-a-message) of your message.

## Deleting messages

If you wish you hadn't sent a message at all, **deleting the content
of the message in the editing UI** will cause the message to be
displayed as `(deleted)`.  The original sender and timestamp of the
message will still be displayed, and the original content of the
message is still accessible via Zulip's edit history feature.  This
can be the least confusing option for other users.

### Delete a message completely

For cases where someone accidentally shared secret information
publicly (e.g.  you posted an employee's salary), one can completely
delete a message from Zulip by following the instructions below.

It's important to understand that anyone who received the message
before you deleted it could have made a copy of its content. So if you
accidentally shared secret information that you can change, like a
password, you may want to change that password regardless of whether
you also delete the message.

{!admin-only.md!}
{!message-actions.md!}
{!down-chevron.md!}

2. Select the **Delete message** option from the dropdown to delete that message.
