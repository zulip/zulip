# Roles and permissions

Zulip offers several levels of permissions based on a
[user's role](/help/roles-and-permissions) in a Zulip organization.

Here are some important details to note when working with these
roles and permissions in Zulip's API:

## A user's role

A user's account data include a `role` property, which contains the
user's role in the Zulip organization. These roles are encoded as:

* Organization owner: 100

* Organization administrator: 200

* Organization moderator: 300

* Member: 400

* Guest: 600

User account data also include these boolean properties that duplicate
the related roles above:

* `is_owner` specifying whether the user is an organization owner.

* `is_admin` specifying whether the user is an organization administrator.

* `is_guest` specifying whether the user is a guest user.

These are intended as conveniences for simple clients, and clients
should prefer using the `role` field, since only that one is updated
by the [events API](/api/get-events).

Note that [`POST /register`](/api/register-queue) also returns an
`is_moderator` boolean property specifying whether the current user is
an organization moderator.

Additionally, user account data include an `is_billing_admin` property
specifying whether the user is a billing administrator for the Zulip
organization, which is not related to one of the roles listed above,
but rather allows for specific permissions related to billing
administration in [paid Zulip Cloud plans](https://zulip.com/plans/).

### User account data in the API

Endpoints that return the user account data / properties mentioned
above are:

* [`GET /users`](/api/get-users)

* [`GET /users/{user_id}`](/api/get-user)

* [`GET /users/{email}`](/api/get-user-by-email)

* [`GET /users/me`](/api/get-own-user)

* [`GET /events`](/api/get-events)

* [`POST /register`](/api/register-queue)

Note that the [`POST /register` endpoint](/api/register-queue) returns
the above boolean properties to describe the role of the current user,
when `realm_user` is present in `fetch_event_types`.

Additionally, the specific events returned by the
[`GET /events` endpoint](/api/get-events) containing data related
to user accounts and roles are the [`realm_user` add
event](/api/get-events#realm_user-add), and the
[`realm_user` update event](/api/get-events#realm_user-update).

## Permission levels

Many areas of Zulip are customizable by the roles
above, such as (but not limited to) [restricting message editing and
deletion](/help/restrict-message-editing-and-deletion) and
[streams permissions](/help/channel-permissions). The potential
permission levels are:

* Everyone / Any user including Guests (least restrictive)

* Members

* Full members

* Moderators

* Administrators

* Owners

* Nobody (most restrictive)

These permission levels and policies in the API are designed to be
cutoffs in that users with the specified role and above have the
specified ability or access. For example, a permission level documented
as 'moderators only' includes organization moderators, administrators,
and owners.

Note that specific settings and policies in the Zulip API that use these
permission levels will likely support a subset of those listed above.

## Determining if a user is a full member

When a Zulip organization has set up a [waiting period before new members
turn into full members](/help/restrict-permissions-of-new-members),
clients will need to determine if a user's account has aged past the
organization's waiting period threshold.

The `realm_waiting_period_threshold`, which is the number of days until
a user's account is treated as a full member, is returned by the
[`POST /register` endpoint](/api/register-queue) when `realm` is present
in `fetch_event_types`.

Clients can compare the `realm_waiting_period_threshold` to a user
accounts's `date_joined` property, which is the time the user account
was created, to determine if a user has the permissions of a full
member or a new member.
