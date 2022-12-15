# Restrict stream creation

{!admin-only.md!}

Zulip allows you to separately control [permissions](/help/roles-and-permissions)
for creating [web-public](/help/public-access-option), public and private
streams.

For corporations and other organizations with controlled access, we
recommend keeping stream creation open to make it easy for users to
self-organize.

Only users in trusted roles (moderators and administrators) can be
given permission to create web-public streams. This is intended
[to help manage abuse](/help/public-access-option#managing-abuse) by
making it hard for an attacker to host malicious content in an
unadvertised web-public stream in a legitimate organization.

### Manage who can create streams

{start_tabs}

{tab|public-streams}

{settings_tab|organization-permissions}

1. Under **Stream permissions**, configure **Who can create public streams**.

{!save-changes.md!}

{tab|private-streams}

{settings_tab|organization-permissions}

1. Under **Stream permissions**, configure **Who can create private streams**.

{!save-changes.md!}

{tab|web-public-streams}

{settings_tab|organization-permissions}

1. Under **Stream permissions**, configure **Who can create web-public streams**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Create a stream](/help/create-a-stream)
* [Roles and permissions](/help/roles-and-permissions)
