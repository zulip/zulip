# Manage inactive streams

In normal Zulip usage, streams fall in and out of use. By default, Zulip
automatically moves streams that haven't been used in a while to the
**Inactive** section at the bottom of your streams list in the left sidebar.
This helps prevent low-traffic streams from cluttering the left sidebar.

You can configure Zulip to move (demote) inactive streams more or less
aggressively. This is an advanced setting; you can safely ignore it if this
is your first time using Zulip.

### Manage inactive streams

{start_tabs}

{settings_tab|preferences}

2. Under **Advanced**, configure **Demote inactive streams**.

{end_tabs}

The default is **Automatic**, which demotes inactive streams once you're
subscribed to a minimum total number of streams. **Always** and **Never**
either demote or don't demote inactive streams regardless of how many
streams you have.
