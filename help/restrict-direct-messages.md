# Restrict direct messages

{!admin-only.md!}

In Zulip, users can exchange direct messages with other users,
[bots](/help/bots-overview) and themselves. Organization
administrators can configure who is allowed to use direct messages.

## Configure who can use direct messages

!!! warn ""

    This feature is beta; see the notes below for details.

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Other permissions**, configure **Who can use direct messages**.

{!save-changes.md!}

{end_tabs}

### Notes on restricting direct messages

* Disabling direct messages will cause sending a direct message to
throw an error; the Zulip UI will appear to still allow direct
messages. We expect to make some UI adjustments when direct messages
are disabled during the beta period.

* Even if direct messages are disabled, users can still exchange
direct messages with bot users (this detail is important for
Zulip's new user onboarding experience). Consider also [restricting
bot creation](/help/restrict-bot-creation) when using this feature.

* Restricting direct messages does not automatically [restrict creating
private channels](/help/configure-who-can-create-channels).
