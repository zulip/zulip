# Edit a message

Zulip makes it possible to edit the content of your messages, letting you fix
typos, clarify your thoughts, etc. Organization administrators can
[configure](/help/restrict-message-editing-and-deletion) who can edit messages,
and set time limits for this action. However, even organization owners cannot
edit the content of a message sent by another user.

!!! tip ""

    You can also [edit message topics](/help/rename-a-topic).

## Edit a message

{start_tabs}

{tab|desktop-web}

{!message-actions.md!}

1. Click the **pencil** (<i class="zulip-icon zulip-icon-edit"></i>) icon. If you do not see
   the **pencil** (<i class="zulip-icon zulip-icon-edit"></i>) icon, you do not have
   permission to edit this message.

1. Edit the content of the message.

1. Click **Save**.

{tab|mobile}

{!message-long-press-menu.md!}

1. Tap **Edit message**. If you do not see the **Edit message** option, you do
   not have permission to edit this message.

1. Edit the content of the message.

1. Tap **Save**.

{end_tabs}

!!! tip ""

    When you edit a message, everyone will see it labeled as **edited**. You
    can [view a message's edit history](/help/view-a-messages-edit-history)
    if it is [allowed](/help/restrict-message-edit-history-access) in your
    organization.

## Message notifications

If you edit a message to [mention a user or group](/help/mention-a-user-or-group),
the newly mentioned users will receive notifications just as if they had been
mentioned in the original message.

If you edit a message soon after sending it, the edit will be reflected in any
[email notifications that have not yet been sent](/help/email-notifications#configure-delay-for-message-notification-emails).
This includes canceling notifications for users whose
[mention](/help/format-your-message-using-markdown#mention-a-user-or-group) was
removed or changed from a regular mention to a
[silent mention](/help/mention-a-user-or-group#silently-mention-a-user).

If you [delete the content of a message](/help/delete-a-message#delete-message-content),
any pending email notifications for that message will be canceled, including
[mentions and alerts](/help/dm-mention-alert-notifications).

## Related articles

* [View, copy, and share message content as Markdown](/help/view-the-markdown-source-of-a-message)
* [Restrict message editing and deletion](/help/restrict-message-editing-and-deletion)
* [Delete a message](/help/delete-a-message)
