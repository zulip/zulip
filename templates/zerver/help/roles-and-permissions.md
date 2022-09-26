# Roles and permissions

There are several possible roles in a Zulip organization.

* **Organization owner**: Can manage users, public streams,
  organization settings, and billing.

* **Organization administrator**: Can manage users, public streams,
  and organization settings.  Cannot create or demote organization
  owners.

* **Moderator**: Have the permissions of full members; additionally,
  many **Organization permissions** settings allow moderators to be
  given additional privileges or do so by default.

* **Member**: Has access to all public streams.  Member is the default
  role for most users.  [Some organization
  settings](/help/restrict-permissions-of-new-members) allow an
  organization to restrict the permissions of **new members**; Members
  who do not have those restrictions are called **full members**.

* **Guest**: Can only view or access streams they've been added to.
  Guest users interact with public streams as though they were private
  streams with shared history.  Cannot create new streams or invite
  other users.

* **Billing administrator**: The user who upgrades the organization to
  a paid plan is, in addition to their normal role, a billing
  administrator.  Can manage billing in addition to the existing
  privileges.  This allows someone from the billing department to
  manage billing without needing organization administrator
  permissions.

For details of the access control model, see [Stream
permissions](/help/stream-permissions).  You can decide what role to
invite a user as when you [send them an
invitation](/help/invite-new-users).

Organization owners can do anything an organization administrator can
do.  For brevity, we may sometimes refer to "organization
administrators" being able to do something; unless stated explicitly,
this means "organization owners and administrators" can do that thing.

## Related articles

* [Stream permissions](/help/stream-permissions)
* [Inviting new users](/help/invite-new-users)
* [Zulip Cloud billing](/help/zulip-cloud-billing)
