# Deactivate or reactivate a user

{!admin-only.md!}

Follow the following steps to deactivate or reactivate any user's account in your
organization.

## Deactivate a user

To properly remove a user’s access to a Zulip organization, it does
not suffice to change their password or deactivate their account in an
email system, since neither of those actions prevents authentication
with the user’s API key or any API keys of the bots the user has
created.

Instead, you should deactivate the user’s account using the Zulip
**[organization administration interface](/help/change-your-organization-settings)**;
this will also automatically deactivate any bots the user has created.

1. Go to the [Users](/#organization/user-list-admin)
{!admin.md!}

 4. Click the **Deactivate** button to the right of the user account that you
want to deactivate.

4. After clicking the **Deactivate** button, a modal window titled
**Deactivate (user's email address)** will appear.

5. To confirm the deactivation of the user's account, click the **Deactivate now**
button. Please note that any bots that the user maintains will be
disabled.

6. After clicking the **Deactivate now** button, the button will transform into
a **Reactivate** button, and the **Make admin** button will also
disappear, confirming the success of the account's deactivation.

    The user will be logged out immediately and returned to the Zulip login page
    and will not be able to log back in.

## Reactivate a user

Zulip organization administrators can choose to reactivate a user's deactivated account
by following the following steps.

1. Go to the [Deactivated users](/#organization/deactivated-users-admin)
{!admin.md!}

4. Click the **Reactivate** button to the right of the user account that you
want to reactivate.

5. After clicking the **Reactivate** button, the button will transform into a
**Deactivate** button, confirming the success of the account's reactivation.
