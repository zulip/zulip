# Deactivate or reactivate a user

{!admin-only.md!}

## Deactivate (ban) a user

To properly remove a user’s access to a Zulip organization, it does not
suffice to change their password or deactivate their account in an external
email system, since the user’s API key and bot API keys will still be
active. Instead, you need to deactivate the user’s account using the Zulip
administrative interface.

Note that organization administrators cannot deactivate organization owners.

{start_tabs}

{tab|via-user-profile}

1. Hover over a user's name in the right sidebar.

1. Click on the ellipsis (<i class="zulip-icon zulip-icon-ellipsis-v-solid"></i>)
   to the right of their name.

1. Click **Manage this user**.

1. Click the **Deactivate user** button at the bottom.

1. Approve by clicking **Deactivate**.

{tab|via-organization-settings}

{settings_tab|user-list-admin}

1. Click the **Deactivate** button to the right of the user account that you
   want to deactivate.

1. Approve by clicking **Deactivate**.

{end_tabs}

The user will be logged out immediately and not be able to log back in. The
user's bots will also be deactivated. Lastly, the user will be unable to
create a new Zulip account in your organization using their deactivated
email address.

## Reactivate a user

Organization administrators can reactivate a deactivated user. The reactivated
user will have the same role, stream subscriptions, user group memberships, and
other settings and permissions as they did prior to deactivation. They will also
have the same API key and bot API keys, but the bots will be deactivated until
the user manually [reactivates](deactivate-or-reactivate-a-bot) them again.

{start_tabs}

{settings_tab|deactivated-users-admin}

4. Click the **Reactivate** button to the right of the user account that you
want to reactivate.

{end_tabs}

!!! tip ""
    You may want to [review and adjust](/help/manage-user-stream-subscriptions)
    the reactivated user's stream subscriptions.
