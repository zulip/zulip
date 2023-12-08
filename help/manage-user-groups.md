# Manage user groups

## Create a user group

{!how-to-create-a-user-group.md!}

## User group options

There are several parameters you can set while creating a user group. All of
which you can change later.

* **User group name**: The user group name can be in any language, and can
  include spaces and other punctuation.

* **User group description**: Lets users know what the group is used for.

* **Who can mention this group?**: Configures who is allowed to
  [mention this group](/help/mention-a-user-or-group).

* **Choose members**: You can copy the membership from an existing stream or
  user group, add all users, or enter users one by one.

## Change a user group's name or description

{start_tabs}

{tab|desktop-web}

{relative|group|all}

1. Select a user group.

1. Select the **General** tab on the right.

1. Click the **pencil** (<i class="fa fa-pencil"></i>) icon
   to the right of the user group, and enter a new name or description.

{!save-changes.md!}

{end_tabs}

## Configure who can mention a user group

{start_tabs}

{tab|desktop-web}

{relative|group|all}

1. Select a user group.

1. Select the **General** tab on the right.

1. Under **Group permissions**, configure **Who can mention this group**.

{!save-changes.md!}

{end_tabs}

## Add users to a user group

{start_tabs}

{tab|desktop-web}

{relative|group|all}

1. Select a user group.

1. Select the **Members** tab on the right.

1. Under **Add members**, enter a name or email address. The typeahead
   will only include users who aren't already members of the group.

1. Click **Add**. Zulip will notify everyone who is added to the group.

!!! tip ""

    To add users in bulk, you can copy members from an
    existing stream or user group.

{end_tabs}

## Remove users from a user group

{start_tabs}

{tab|desktop-web}

{relative|group|all}

1. Select a user group.

1. Select the **Members** tab on the right.

1. Under **Members**, find the user you would like to remove.

1. Click the **Remove** button in that row. Zulip will notify everyone who is
   removed from the group.

!!! warn ""

    **Note**: If you remove yourself from a user group, you
    may no longer have permission to modify the user group.

{end_tabs}

## Delete a user group

{start_tabs}

{tab|desktop-web}

{relative|group|all}

1. Select a user group.

1. Click the **trash** <i class="fa fa-trash-o"></i> icon near the top right
   corner of the user group settings panel.

1. Approve by clicking **Confirm**.

!!! warn ""

    **Note**: Deleting a user group cannot be undone by anyone.

{end_tabs}

## Configure who can create and manage user groups

{!admin-only.md!}

By default, [all members](/help/roles-and-permissions) in a Zulip
organization can create user groups and manage user groups that they
are a member of. However, you can restrict that ability to specific
[roles](/help/roles-and-permissions).

Note that administrators and moderators can modify any user group,
while other organization members can only modify user groups to which
they belong. Guests cannot modify or create user groups.

{start_tabs}

{tab|desktop-web}

{settings_tab|organization-permissions}

1. Under **Other permissions**, configure **Who can create and manage user groups**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [User groups](/help/user-groups)
* [Mention a user or group](/help/mention-a-user-or-group)
* [Create user groups](/help/create-user-groups)
* [Setting up your organization](/help/getting-your-organization-started-with-zulip)
* [Roles and permissions](/help/roles-and-permissions)
