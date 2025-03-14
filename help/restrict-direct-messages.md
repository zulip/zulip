# Restrict direct messages

{!admin-only.md!}

Organization administrators can configure two types of permissions for [direct
messages](/help/direct-messages):

- Who can **authorize** a direct message conversation. To send a DM, the recipients
  must include at least one user who can authorize the conversation (the sender
  or someone else).
- Who can **start** a direct message conversation.

These permissions can be granted to any combination of
[roles](/help/user-roles), [groups](/help/user-groups), and individual
[users](/help/introduction-to-users). They are designed so that users can always
respond to a direct message they've received (unless organization permissions
change). They also provide a lot of flexibility for managing DMs in your
organization. For example, you can:

- Prevent 1:1 DMs between [guest users](/help/guest-users).
- Allow members to respond to DMs from an admin or moderator, but not to start
  DM conversations.
- Disable direct messages altogether.

Regardless of how these settings are configured, users can always send direct messages
to bots and to themselves.

!!! tip ""

    When restricting direct messages, consider also [restricting who can create
    private channels](/help/configure-who-can-create-channels).

## Configure who can authorize a direct message conversation

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Direct message permissions**, configure **Who can authorize a direct
   message conversation**.

{!save-changes.md!}

{end_tabs}

## Configure who can start a direct message conversation

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Direct message permissions**, configure **Who can start a direct
   message conversation**.

{!save-changes.md!}

{end_tabs}

## Disable direct messages

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Direct message permissions**, set **Who can authorize a direct
   message conversation** to **Direct messages disabled**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Direct messages](/help/direct-messages)
* [Restrict channel creation](/help/configure-who-can-create-channels)
