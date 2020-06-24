# Change a user's role

{!admin-only.md!}

Users join as [owners, administrators, members, or
guests](/help/roles-and-permissions), depending on how they were
invited.

An organization owner can change the role of any user.  An
organization administrator can change the role of most users, but
cannot create or demote an organization owner.

You can can revoke your own owner or administrative privileges if
there is at least one other owner in the organization (Consider
promoting a new owner or [deactivating the
organization](/help/deactivate-your-organization) instead).

**Changes** Organization owners were introduced in Zulip 3.0; users
that were marked as administrators in older Zulip instances are
automatically converted during the upgrade to Zulip 3.0 into owners
(who have the same permissions as administrators did previously).

### Change a user's role

{start_tabs}

{settings_tab|user-list-admin}

1. Find the user you would like to manage. Click the **pencil**
(<i class="fa fa-pencil"></i>) to the right of their name.

1. Under **User role**, select **Owner**, **Administrator**, **Member** or **Guest**.

1. Click **Save changes**. The new rights will take effect immediately.

{end_tabs}
