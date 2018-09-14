# Deactivate or reactivate a user

{!admin-only.md!}

## Deactivate (ban) a user

To properly remove a user’s access to a Zulip organization, it does not
suffice to change their password or deactivate their account in an external
email system, since the user’s API key and bot API keys will still be
active. Instead, you need to deactivate the user’s account using the Zulip
administrative interface.

{settings_tab|user-list-admin}

 4. Click the **Deactivate** button to the right of the user account that you
want to deactivate.

4. Click **Deactivate now** to confirm.

The user will be logged out immediately and not be able to log back in. The
user's bots will also be deactivated. Lastly, the user will be unable to
create a new Zulip account in your organization using their deactivated
email address.

## Reactivate a user

Organization administrators can reactivate a deactivated user. They will
have the same API key and bot API keys, but the bots will be deactivated
until the user manually [reactivates](deactivate-or-reactivate-a-bot) them
again.

{settings_tab|deactivated-users-admin}

4. Click the **Reactivate** button to the right of the user account that you
want to reactivate.
