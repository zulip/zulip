# User roles

{!user-roles-intro.md!}

You can also manage permissions with [custom user groups](/help/user-groups).

## Roles

* **Organization owner**: Can manage users, public channels, organization
  settings, and billing. Organization owners can do anything that an
  organization administrator can do.

* **Organization administrator**: Can manage users, public channels, and
  organization settings. Cannot make someone an owner, or change an existing
  owner's role.

* **Moderator**: Can do anything that members can do, plus additional
  permissions [configured](/help/manage-permissions) by
  your organization.

* **Member**: This is the default role for most users. Members have access to
  all public channels. You can [configure different
  permissions](/help/restrict-permissions-of-new-members) for **new members**
  and **full members**, which is especially useful for [moderating open
  organizations](/help/moderating-open-organizations). New members automatically
  become full members after a configurable waiting period.

* **Guest**: Can view and send messages in channels they have been subscribed to.
  Guests cannot see other channels, unless they have been specifically subscribed
  to the channel. See [guest users documentation](/help/guest-users) for additional
  details and configuration options.

* **Billing administrator**: The user who upgrades the organization to
  a paid plan is, in addition to their normal role, a billing
  administrator.  Billing administrators can manage billing for the organization.
  For example, someone from your billing department can be a **billing
  administrator**, but not an **administrator** for the organization.

## View users by role

{!view-users-by-role.md!}

## Change a user's role

{!admin-only.md!}

An organization owner can change the role of any user. You can make yourself no
longer an owner only if there is at least one other owner for your organization.
An organization administrator cannot make someone an owner, or change an
existing owner's role.

{start_tabs}

{tab|via-user-profile}

{!manage-this-user.md!}

1. Under **User role**, select a [role](#roles).

1. Click **Save changes**. The new permissions will take effect immediately.

{!manage-user-tab-tip.md!}

{tab|via-organization-settings}

{settings_tab|users}

1. Find the user you would like to manage. Click the **manage bot**
   (<i class="zulip-icon zulip-icon-user-cog"></i>) icon to the right
   of their name.

1. Under **User role**, select a [role](#roles).

1. Click **Save changes**. The new permissions will take effect immediately.

{end_tabs}

## Related articles

* [Guest users](/help/guest-users)
* [User groups](/help/user-groups)
* [Manage permissions](/help/manage-permissions)
* [Manage a user](/help/manage-a-user)
* [Deactivate or reactivate a user](/help/deactivate-or-reactivate-a-user)
