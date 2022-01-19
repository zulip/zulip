# Configure who can use private messages

{!admin-only.md!}

By default, any user can send private messages.  Organization
administrators can change who is allowed to use private messages.

### Configure who can use private messages

!!! warn ""

    This feature is beta; see the notes below for details.

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Other permissions**, configure **Who can use private messages**.

{!save-changes.md!}

{end_tabs}

### Notes on restricting private messages

* Disabling private messages will cause sending a private message to
throw an error; the Zulip UI will appear to still allow private
messages.  We expect to make some UI adjustments when private messages
are disabled during the beta period.
* Even if private messages are disabled, users can still exchange
direct private messages with bot users (this detail is important for
Zulip's new user onboarding experience).  Consider also [restricting
bot creation](/help/restrict-bot-creation) when using this feature.
* Restricting private messages does not automatically [restrict creating
  private streams](/help/restrict-permissions-of-new-members).
