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
- The user is subscribed to one or more [streams](/help/streams-and-topics) with
  the guest.

When a guest cannot see information about a user, the guest's experience will be
that:

- The user does not appear in the right sidebar.
- The user does not appear in typeahead suggestions, e.g., in the compose box
  and search.
- Otherwise, such a user will be displayed as an **Unknown user** in the Zulip
  app. For example, messages and reactions from a former subscriber of a stream
  will be shown as from an **Unknown user**.
- An **Unknown user**'s [user card](/help/user-cards) will not display
  information about that user. However, the guest can still search from all
  messages send by a particular **Unknown user** from that user's card.

In practice, guests should rarely encounter content from an **Unknown user**,
unless users in your organization frequently change their stream subscriptions
or are [deactivated](/help/deactivate-or-reactivate-a-user).

The only information guests can access about unknown users via the [API](/api)
is which user IDs exist.

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
