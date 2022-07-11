# Add or remove users from a stream

## Add users to a stream

By default, anyone (other than guests) subscribed to a stream can add
users to that stream. Additionally, anyone (other than guests) can add
users to a public stream, whether or not they are subscribed to the
stream.

Organization administrators can configure which
[roles](/help/roles-and-permissions) have access to [add other users
to a stream][configure-invites].

{start_tabs}

{relative|stream|all}

1. Select a stream.

{!select-stream-view-subscribers.md!}

1. Under **Add subscribers**, enter a name or email address. The typeahead
   will only include users who aren't already subscribed to the stream.

1. Click **Add**.

{end_tabs}

!!! tip ""

      To add users in bulk, you can copy members from an
      existing stream or [user group](/help/user-groups).

### Mentioning a user in the compose box (alternate method)

When you [mention a user](/help/mention-a-user-or-group) while composing
a message, an alert banner appears above the compose box if they are not
subscribed to the stream.

Click the **Subscribe them** button on the banner to add the user to the
stream. You will not see the button if you don't have permission to
subscribe the user.

!!! tip ""

      You do not have to send the message you are composing for
      the user to be subscribed this way.

## Remove users from a stream

{!admin-only.md!}

Anyone can always [unsubscribe themselves from a stream](/help/unsubscribe-from-a-stream).

Organization administrators can also unsubscribe *other* users from any stream,
including streams the admin is not subscribed to.

{start_tabs}

{relative|stream|all}

1. Select a stream.

{!select-stream-view-subscribers.md!}

1. Under **Subscribers**, find the user you would like to remove.

1. Click the **Unsubscribe** button in that row.

{end_tabs}

[configure-invites]: /help/configure-who-can-invite-to-streams

### From a user's profile (alternate method)

This method is useful if you need to remove one user from multiple streams.

{start_tabs}

{!right-sidebar-view-full-profile.md!}

1. Select the **Streams** tab.

1. Under **Subscribed streams**, find the stream you would like
   to remove the user from.

1. Click the **Unsubscribe** button in that row.

{end_tabs}

## Related articles

* [Browse and subscribe to streams](/help/browse-and-subscribe-to-streams)
* [Unsubscribe from a stream](/help/unsubscribe-from-a-stream)
* [Manage a user's stream subscriptions](/help/manage-user-stream-subscriptions)
* [Restrict stream invitation](/help/configure-who-can-invite-to-streams)
* [Set default streams for new users](/help/set-default-streams-for-new-users)
* [Roles and permissions](/help/roles-and-permissions)
* [Mention a user or group](/help/mention-a-user-or-group)
