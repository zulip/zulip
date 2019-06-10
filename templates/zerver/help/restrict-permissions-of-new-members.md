# Waiting period for full members

{!admin-only.md!}

Some organization settings allow permissions to be limited to all members or just full members.
Full members are members whose accounts are older than the configured waiting period which can be
configured as:

* **No waiting period**
* **Members with accounts less than 3 days old**
* **Members with accounts less than N days old**, for some `N`.

This functionality can be useful to limit what "disruptive features" a new user has access to
until they are familiar with Zulip and the rules of your organization.

For large Zulips where anyone can join, we recommend setting the waiting period
to at least a few days old (we suggest starting with `N = 3`), to make it easier to cope with
spammers and confused users.

Currently, the following permissions support limiting access to only full members:

- [**Configure who can create streams**](/help/configure-who-can-create-streams)
- [**Configure who can invite to streams**](/help/configure-who-can-invite-to-streams)

### Manage the waiting period

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Other permissions**, configure **Waiting period before new members turn into full members**.

{!save-changes.md!}

{end_tabs}
