# Restrict moving messages

Zulip lets you configure who can edit message topics and move topics between
channels. These permissions can be granted to any combination of
[roles](/help/user-roles), [groups](/help/user-groups), and individual
[users](/help/introduction-to-users).

In addition to granting organization-wide permissions, you can configure
permissions for each channel. For example, you could allow the "engineering"
group to move messages just in the #engineering channel.

In general, allowing all organization members to edit message topics is highly
recommended because:

- It allows the community to keep conversations organized, even if some members
  are still learning how to use topics effectively.
- It makes it possible to fix a typo in the topic of a message you just sent.

You can let users edit topics without a time limit, or prohibit topic editing on
older messages to avoid potential abuse. The time limit will never apply to
administrators and moderators.

Permissions for moving messages between channels can be configured separately.

## Configure who can edit topics in any channel

{!admin-only.md!}

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Moving messages**, configure **Who can edit topics in any channel**.

{!save-changes.md!}

{end_tabs}

## Configure who can edit topics in a specific channel

{start_tabs}

{tab|desktop-web}

{relative|channel|all}

1. Select a channel.

{!select-channel-view-general-advanced.md!}

1. Under **Moderation permissions**, configure **Who can move messages inside this
   channel**.

{!save-changes.md!}

{end_tabs}

## Set a time limit for editing topics

!!! tip ""
    The time limit you set will not apply to administrators and moderators.

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Moving messages**, configure **Time limit for editing topics**.

{!save-changes.md!}

{end_tabs}

## Configure who can move messages out of any channel

{!admin-only.md!}

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Moving messages**, configure **Who can move messages out of any channel**.

{!save-changes.md!}

{end_tabs}

## Configure who can move messages to another channel from a specific channel

{start_tabs}

{tab|desktop-web}

{relative|channel|all}

1. Select a channel.

{!select-channel-view-general-advanced.md!}

1. Under **Moderation permissions**, configure **Who can move messages out of this
   channel**.

{!save-changes.md!}

{end_tabs}


## Set a time limit for moving messages between channels

!!! tip ""
    The time limit you set will not apply to administrators and moderators.

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Moving messages**, configure **Time limit for  moving messages
   between channels**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Rename a topic](/help/rename-a-topic)
* [Resolve a topic](/help/resolve-a-topic)
* [Move content to another topic](/help/move-content-to-another-topic)
* [Move content to another channel](/help/move-content-to-another-channel)
* [Restrict message editing and deletion](/help/restrict-message-editing-and-deletion)
* [Restrict resolving topics](/help/restrict-resolving-topics)
* [Restrict message edit history access](/help/restrict-message-edit-history-access)
* [User roles](/help/user-roles)
