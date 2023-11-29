# Guest users

You can add users who should have restricted access to your organization as
**guests**. For example, this may be a good choice for contractors or customers
invited to a company's Zulip chat.

Guest users **can**:

- View and send messages in streams they have been added to, including viewing
  message history in the same way as other stream subscribers.

Guest users **cannot**:

- See private or public streams, unless they have been specifically added to the stream.
- Create new streams or user groups.
- Add or manage bots.
- Add custom emoji.
- Invite users to join the organization.

You can also **configure** other permissions for guest users, such as whether they
can:

- [Move](/help/restrict-moving-messages) or
  [edit](/help/restrict-message-editing-and-deletion) messages.
- Notify a large number of users [with a wildcard
  mention](/help/restrict-wildcard-mentions).

Zulip Cloud plans have [special discounted
pricing](/help/zulip-cloud-billing#temporary-users-and-guests) for guest users.

## Configure guest indicator

{start_tabs}

{tab|desktop-web}

{settings_tab|organization-permissions}

1. Under **Guests**, toggle **Display “(guest)” after names of guest users**.

{!save-changes.md!}

{end_tabs}

## Configure whether guests can see all other users

{!cloud-plus-only.md!}

You can restrict guests' ability to see other users in the organization. If you
do so, guests will be able to see information about other users only in the
following cases:

- The user belongs to a [direct message](/help/direct-messages) thread with the
  guest.
- The user is subscribed to the same [stream](/help/streams-and-topics) as the
  guest.

All other users will be displayed as **Unknown users** in the Zulip app. For
example, messages and reactions from a former subscriber of a stream will be
shown as from an **Unknown user**. Unknown users are not shown in the guest's
right sidebar, and cannot be accessed by guests via the [API](/api).

{start_tabs}

{tab|desktop-web}

{settings_tab|organization-permissions}

1. Under **Guests**, configure **Who can view all other users in the
   organization**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Roles and permissions](/help/roles-and-permissions)
* [Invite new users](/help/invite-new-users)
* [Change a user's role](/help/change-a-users-role)
* [Zulip Cloud billing](/help/zulip-cloud-billing)
