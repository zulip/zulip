# Restrict moving messages

{!admin-only.md!}

Zulip lets you configure which [roles](/help/roles-and-permissions) can edit
message topics and move topics between channels. In general, allowing all
organization members to edit message topics is highly recommended because:

- It allows the community to keep conversations organized, even if some members
  are still learning how to use topics effectively.
- It lets users [resolve topics](/help/resolve-a-topic).
- It makes it possible to fix a typo in the topic of a message you just sent.

You can let users edit topics without a time limit, or prohibit topic editing on
older messages to avoid potential abuse. The time limit will never apply to
administrators and moderators.

Permissions for moving messages between channels can be configured separately.

## Configure who can edit topics

!!! tip ""
    Anyone can add a topic to messages sent without a topic.

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Moving messages**, configure **Who can move messages to another
   topic**.

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

## Configure who can move messages to another channel

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Moving messages**, configure **Who can move messages to another
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
* [Restrict message editing and
  deletion](/help/restrict-message-editing-and-deletion)
* [Roles and permissions](/help/roles-and-permissions)
