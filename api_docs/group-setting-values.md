# Group-setting values

Settings defining permissions in Zulip are increasingly represented
using [user groups](/help/user-groups), which offer much more flexible
configuration than the older [roles](/api/roles-and-permissions) system.

!!! warn ""

    **Note**: Many group-valued settings are configured to require
    a single system group for their value via
    `server_supported_permission_settings`, pending web app UI
    changes to fully support group-setting values.

    **Changes**: Before Zulip 10.0 (feature level 309), only system
    groups were permitted values for group-setting values in
    production environments, regardless of the values in
    `server_supported_permission_settings`.

In the API, these settings are represented using a **group-setting
value**, which can take two forms:

- An integer user group ID, which can be either a named user group
  visible in the UI or a [role-based system group](#system-groups).
- An object with fields `direct_member_ids`, containing a list of
  integer user IDs, and `direct_subgroup_ids`, containing a list of
  integer group IDs. The setting's value is the union of the
  identified collection of users and groups.

Group-setting values in the object form can be thought of as an
anonymous group. They function very much like a named user group
object, and remove the naming and UI overhead involved in creating
a visible user group just to store the value of a single setting.

The server will canonicalize an object with an empty `direct_member_ids`
list and a `direct_subgroup_ids` list that contains just a single group
ID to the integer format.

## System groups

The Zulip server maintains a collection of system groups that
correspond to the users with a given role; this makes it convenient to
store concepts like "all administrators" in a group-setting
value. These use a special naming convention and can be recognized by
the `is_system_group` property on their group object.

The following system groups are maintained by the Zulip server:

- `role:internet`: Everyone on the Internet has this permission; this
  is used to configure the [public access
  option](/help/public-access-option).
- `role:everyone`: All users, including guests.
- `role:members`: All users, excluding guests.
- `role:fullmembers`: All [full
  members](https://zulip.com/api/roles-and-permissions#determining-if-a-user-is-a-full-member)
  of the organization.
- `role:moderators`: All users with at least the moderator role.
- `role:administrators`: All users with at least the administrator
  role.
- `role:owners`: All users with the owner role.
- `role:nobody`: The formal empty group. Used in the API to represent
  disabling a feature.

Client UI for setting a permission or displaying a group (when
silently mentioned, for example) is encouraged to display system
groups using their description, rather than using their `role:}`
names, which are chosen to be unique and clear in the API.

System groups should generally not be displayed in UI for
administering an organization's user groups, since they are not
directly mutable.

## Updating group-setting values

The Zulip API uses a special format for modifying an existing setting
using a group-setting value.

A **group-setting update** is an object with a `new` field and an
optional `old` field, each containing a group-setting value. The
setting's value will be set to the membership expressed by the `new`
field.

The `old` field expresses the client's understanding of the current
value of the setting. If the `old` field is present and does not match
the actual current value of the setting, then the request will fail
with error code `EXPECTATION_MISMATCH` and no changes will be applied.

When a user edits the setting in a UI, the resulting API request
should generally always include the `old` field, giving the value
the list had when the user started editing. This accurately expresses
the user's intent, and if two users edit the same list around the
same time, it prevents a situation where the second change
accidentally reverts the first one without either user noticing.

Omitting `old` is appropriate where the intent really is a new complete
list rather than an edit, for example in an integration that syncs the
list from an external source of truth.

## Permitted values

Not every possible group-setting value is a valid configuration for a
given group-based setting. For example, as a security hardening
measure, some administrative permissions should never be exercised by
guest users, and the system group for all users, including guests,
should not be offered to users as an option for those settings.

Others have restrictions to only permit system groups due to UI
components not yet having been migrated to support a broader set of
values. In order to avoid this configuration ending up hardcoded in
clients, every permission setting using this framework has an entry in
the `server_supported_permission_settings` section of the [`POST
/register`](/api/register-queue) response.

Clients that support mutating group-settings values must parse that
part of the `register` payload in order to compute the set of
permitted values to offer to the user and avoid server-side errors
when trying to save a value.

Note specifically that the `allow_everyone_group` field, which
determines whether the setting can have the value of "all user
accounts, including guests" also controls whether guests users can
exercise the permission regardless of their membership in the
group-setting value.
