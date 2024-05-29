# Deactivate or reactivate a user

## Deactivating a user

{!admin-only.md!}

When you deactivate a user:

* The user will be immediately logged out of all Zulip sessions, including
  desktop, web and mobile apps.

* The user's credentials for logging in will no longer work, including password
  login and [any other login options](/help/configure-authentication-methods)
  enabled in your organization.

* The user's [bots](/help/bots-overview) will be deactivated.

* [Email invitations and invite links](/help/invite-new-users) created by the
  user will be disabled.

* Even if your organization [allows users to join without an
  invitation](/help/restrict-account-creation#set-whether-invitations-are-required-to-join),
  this user will not be able to rejoin with the same email account.

!!! warn ""

    You must go through the deactivation process below to fully remove a user's
    access to your Zulip organization. Changing a user's password or removing
    their single sign-on account will not log them out of their open Zulip
    sessions, or disable their API keys.

### Deactivate a user

{start_tabs}

{tab|via-user-profile}

{!manage-this-user.md!}

1. Click **Deactivate user** at the bottom of the **Manage user** menu.

1. *(optional)* Select **Notify this user by email?** if desired, and enter a
   custom comment to include in the notification email.

1. Approve by clicking **Deactivate**.

{!manage-user-tab-tip.md!}

{tab|via-organization-settings}

{settings_tab|user-list-admin}

1. In the **Actions** column, click the **deactivate** (<i class="fa
   fa-user-times"></i>) icon for the user you want to deactivate.

1. *(optional)* Select **Notify this user by email?** if desired, and enter a
   custom comment to include in the notification email.

1. Approve by clicking **Deactivate**.

{end_tabs}

!!! tip ""

    Organization administrators cannot deactivate organization owners.

## Reactivating a user

{!admin-only.md!}

A reactivated user will have the same role, channel subscriptions, user group
memberships, and other settings and permissions as they did prior to
deactivation. They will also have the same API key and bot API keys, but their
bots will be deactivated until the user manually
[reactivates](deactivate-or-reactivate-a-bot) them again.

### Reactivate a user

{start_tabs}

{tab|via-organization-settings}

{settings_tab|deactivated-users-admin}

1. Click the **Reactivate** button to the right of the user account that you
   want to reactivate.

{tab|via-user-profile}

1. Click on a user's profile picture or name on a message they sent
   to open their **user card**.

1. Click **View profile**.

1. Select the **Manage user** tab.

1. Click **Reactivate user** at the bottom of the **Manage user** menu.

1. Approve by clicking **Confirm**.

{!manage-user-tab-tip.md!}

{end_tabs}

!!! tip ""

    You may want to [review and adjust](/help/manage-user-channel-subscriptions)
    the reactivated user's channel subscriptions.

## Related articles

* [Mute a user](/help/mute-a-user)
* [Change a user's role](/help/change-a-users-role)
* [Change a user's name](/help/change-a-users-name)
* [Deactivate your account](/help/deactivate-your-account)
* [Manage a user](/help/manage-a-user)
