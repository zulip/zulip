# Restrict stream creation

{!admin-only.md!}

By default, anyone other than guests can create new streams. However, you can restrict stream
creation to:

* Organization administrators
* Organization administrators and all members
* Organization administrators and [full members](/help/restrict-permissions-of-new-members)

For corporations and other entities with controlled access, we highly
recommend keeping stream creation open. A typical Zulip organization with
heavy use has as many streams as users.

### Manage who can create streams

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Other permissions**, configure **Who can create streams**.

{!save-changes.md!}

{end_tabs}
