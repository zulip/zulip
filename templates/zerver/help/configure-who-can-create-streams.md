# Restrict stream creation

{!admin-only.md!}

By default, anyone other than guests can create new streams. However, you can restrict stream creation to

* **Organization administrators**, or
* **Organization administrators, and members with accounts at least `N` days old**,
  for any `N`.

For corporations and other entities with controlled access, we highly
recommend keeping stream creation open. A typical Zulip organization with
heavy use has as many streams as users.

For large Zulips where anyone can join, we recommend restricting stream
creation to those with accounts at least a few days old (we suggest starting
with `N = 3`), to make it easier to cope with spammers and confused users.

{settings_tab|organization-permissions}

2. Under **Other permissions**, configure **Who can create streams**.

{!save-changes.md!}
