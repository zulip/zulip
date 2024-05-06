# Restrict channel creation

{!admin-only.md!}

Zulip allows you to separately control [permissions](/help/roles-and-permissions)
for creating [web-public](/help/public-access-option), public and private
channels.

For corporations and other organizations with controlled access, we
recommend keeping channel creation open to make it easy for users to
self-organize.

Only users in trusted roles (moderators and administrators) can be
given permission to create web-public channels. This is intended
[to help manage abuse](/help/public-access-option#managing-abuse) by
making it hard for an attacker to host malicious content in an
unadvertised web-public channel in a legitimate organization.

### Manage who can create channels

{start_tabs}

{tab|public-channels}

{settings_tab|organization-permissions}

1. Under **Channel permissions**, configure **Who can create public channels**.

{!save-changes.md!}

{tab|private-channels}

{settings_tab|organization-permissions}

1. Under **Channel permissions**, configure **Who can create private channels**.

{!save-changes.md!}

{tab|web-public-channels}

{settings_tab|organization-permissions}

1. Under **Channel permissions**, configure **Who can create web-public channels**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Create a channel](/help/create-a-channel)
* [Roles and permissions](/help/roles-and-permissions)
