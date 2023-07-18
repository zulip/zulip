# Restrict message editing and deletion

{!admin-only.md!}

Zulip lets you separately configure permissions for editing and deleting
messages, and you can set time limits for both actions. Regardless of the
configuration you select:

* Message content can only ever be modified by the original author.
* Any message can be deleted at any time by an organization administrator.

Note that if a user can edit a message, they can also "delete" it by removing
all the message content. This is different from proper message deletion in two
ways: the original content will still show up in [message edit
history](/help/view-a-messages-edit-history), and will be included in
[exports](/help/export-your-organization). Deletion permanently (and
irretrievably) removes the message from Zulip.

## Configure message editing permissions

!!! tip ""

    Users can only edit their own messages.

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Message editing**:
    - Toggle **Allow message editing**.
    - Configure **Time limit for editing messages**.

{!save-changes.md!}

{end_tabs}

## Configure message deletion permissions

!!! tip ""

    Administrators can always delete any message.

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Message deletion**:
    - Configure **Who can delete their own messages**.
    - Configure **Time limit for deleting messages**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Edit a message](/help/edit-a-message)
* [Delete a message](/help/delete-a-message)
* [Delete a topic](/help/delete-a-topic)
* [Disable message edit history](/help/disable-message-edit-history)
* [Configure message retention policy](/help/message-retention-policy)
* [Restrict moving messages](/help/restrict-moving-messages)
