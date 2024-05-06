# Manage inactive channels

In normal Zulip usage, channels fall in and out of use. By default, Zulip
automatically moves channels that haven't been used in a while to the
**Inactive** section at the bottom of your channels list in the left sidebar.
This helps prevent low-traffic channels from cluttering the left sidebar.

You can configure Zulip to move (demote) inactive channels more or less
aggressively. This is an advanced setting; you can safely ignore it if this
is your first time using Zulip.

### Manage inactive channels

{start_tabs}

{settings_tab|preferences}

2. Under **Advanced**, configure **Demote inactive channels**.

{end_tabs}

The default is **Automatic**, which demotes inactive channels once you're
subscribed to a minimum total number of channels. **Always** and **Never**
either demote or don't demote inactive channels regardless of how many
channels you have.
