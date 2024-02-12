# Roles and permissions

## User roles

User roles make it convenient to configure different permissions for different
users in your organization. You can decide what role a user will have when you
[send them an invitation](/help/invite-new-users), and later [change a user's
role](/help/roles-and-permissions#change-a-users-role) if needed.

!!! tip ""

    Learn about [stream permissions](/help/stream-permissions), including
    **public** and **private** streams.

* **Organization owner**: Can manage users, public streams, organization
  settings, and billing. Organization owners can do anything that an
  organization administrator can do.

* **Organization administrator**: Can manage users, public streams, and
  organization settings. Cannot make someone an owner, or change an existing
  owner's role.

* **Moderator**: Can do anything that members can do, plus additional
  permissions [configured](/help/roles-and-permissions#manage-permissions) by
  your organization.

* **Member**: This is the default role for most users. Members have access to
  all public streams. You can [configure different
  permissions](/help/restrict-permissions-of-new-members) for **new members**
  and **full members**, which is especially useful for [moderating open
  organizations](/help/moderating-open-organizations). New members automatically
  become full members after a configurable waiting period.

* **Guest**: Can view and send messages in streams they have been added to.
  Guests cannot see other streams, unless they have been specifically added to
  the stream. See [guest users documentation](/help/guest-users) for additional
  details and configuration options.

* **Billing administrator**: The user who upgrades the organization to
  a paid plan is, in addition to their normal role, a billing
  administrator.  Billing administrators can manage billing for the organization.
  For example, someone from your billing department can be a **billing
  administrator**, but not an **administrator** for the organization.

## Change a user's role

{!change-a-users-role.md!}

## Manage permissions

{start_tabs}

{settings_tab|organization-permissions}

1. Review organization permissions, and modify as needed.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Change a user's role](/help/change-a-users-role)
* [Stream permissions](/help/stream-permissions)
* [Inviting new users](/help/invite-new-users)
* [Zulip Cloud billing](/help/zulip-cloud-billing)
* [Guest users](/help/guest-users)
