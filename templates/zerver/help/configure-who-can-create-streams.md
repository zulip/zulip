# Restrict stream creation

{!admin-only.md!}

Zulip allows you to separately control permissions for creating public and private streams.
You can restrict stream creation to:

* Organization administrators
* Organization administrators and moderators
* Organization administrators and [full members](/help/restrict-permissions-of-new-members)
* Organization administrators and all members

For corporations and other entities with controlled access, we highly
recommend keeping stream creation open. Open organizations may choose to be
less permissive, especially with public streams.

### Manage who can create streams

{start_tabs}

{tab|public-streams}

{settings_tab|organization-permissions}

2. Under **Stream permissions**, configure **Who can create public streams**.

{!save-changes.md!}

{tab|private-streams}

{settings_tab|organization-permissions}

2. Under **Stream permissions**, configure **Who can create private streams**.

{!save-changes.md!}

{end_tabs}
