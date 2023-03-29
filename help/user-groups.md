# User groups

User groups allow you to [mention](/help/mention-a-user-or-group) multiple
users at once. When you mention a user group, everyone in the group is
[notified](/help/dm-mention-alert-notifications) as if they were
individually mentioned.

Note that user groups are not the same as group direct messages. If you're
trying to send a message to a group of people, you'll want to either
[create a stream](/help/create-a-stream), or send a
[group direct message](/help/direct-messages).

### Create a user group

{!how-to-create-a-user-group.md!}

### Modify a user group

{start_tabs}

{settings_tab|user-groups-admin}

1. Find the group.

1. Click on the group name or description to edit.

1. Add or remove users (including yourself). Click outside the box
   to save.  Zulip will notify everyone who is added or removed.

!!! warn ""
    **Note**: If you remove yourself from a user group, you
    may no longer have permission to modify the user group.

{end_tabs}

### Delete a user group

{start_tabs}

{settings_tab|user-groups-admin}

1. Find the group.

1. Click the **trash** (<i class="fa fa-trash-o"></i>) icon in the top
   right corner of the user group.

1. Approve by clicking **Confirm**.

!!! warn ""
    **Note**: Deleting a user group cannot be undone by anyone.

{end_tabs}

### Configure who can create and manage user groups

{!admin-only.md!}

By default, [all members](/help/roles-and-permissions) in a Zulip
organization can create user groups and manage user groups that they
are a member of. However, you can restrict that ability to specific
[roles](/help/roles-and-permissions).

Note that administrators and moderators can modify any user group,
while other organization members can only modify user groups to which
they belong. Guests cannot modify or create user groups.

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Other permissions**, configure **Who can create and manage user groups**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Mention a user or group](/help/mention-a-user-or-group)
* [Create user groups](/help/create-user-groups)
* [Setting up your organization](/help/getting-your-organization-started-with-zulip)
* [Roles and permissions](/help/roles-and-permissions)
