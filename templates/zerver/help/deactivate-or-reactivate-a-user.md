# Deactivate or reactivate a user

{!admin-only.md!}

## Deactivate a user

To properly remove a user’s access to a Zulip organization, it does not
suffice to change their password or deactivate their account in an email
system, since the user’s API key and bot API keys will still be active.
Instead, you should deactivate the user’s account using the Zulip
organization administration interface.

{settings_tab|user-list-admin}

 4. Click the **Deactivate** button to the right of the user account that you
want to deactivate.

4. A modal window titled **Deactivate (user's email address)** will appear.
Click the **Deactivate now** button.

The user will be logged out immediately and returned to the Zulip login page
and will not be able to log back in.

## Reactivate a user

Zulip organization administrators can choose to reactivate a user's
deactivated account. This will allow a user to use the same email of an
account that has been deactivated, and give access to everything that the
formerly-deactivated user had access to. They will have the same API key and
bot API keys, but the bot API keys will be deactivated until the user manually
reactivates them again.

{settings_tab|deactivated-users-admin}

4. Click the **Reactivate** button to the right of the user account that you
want to reactivate.
