# Users data model

We track different types of users in our browser code.

There are three disjoint sets of users you care about
for typical Zulip realms:

- active users in your realm
- cross-realm users like feedback@zulip.com
- deactivated users in your realm

You can also think in terms of these user populations:

- current realm users (active users in your realm)
- active users (adds cross-realm bots to current realm users)
- all users (adds deactivated users from your realm to active users)

Each of the above categories makes sense for certain UI functions.

Let's start with the features that are restricted to active realm
users, and let's end with features that can apply to all users.

Only current realm users can...
- be subscribed to streams on your realm
- be highlighted in the compose-fade feature
- show up in your buddy list
- show up in your at-mention typeaheads

Active users can...
- be sent PMs to
- show up in your compose recipient typeaheads
- show up in search suggestions

All users can...
- show up in your message stream
- be narrowed to by clicking on recipient bars, etc.
- be narrowed to by searches (but not suggested)
- can show up in your "Private Messages" sidebar

We also have the mirroring world, where we have unknown users
that we can send PMs to, and local-echo is allowed to create
skeleton objects for them.  (Typically with mirrors, we are
dealing with a third-party chat tool like IRC or Zephyr, and
if a user sends a message to a user we don't yet know about,
the third party will confirm that the user exists, and we
subsequently create a "mirror dummy" user on-demand for that
account.)

