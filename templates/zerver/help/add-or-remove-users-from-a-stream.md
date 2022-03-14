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

1. Under **Add subscribers**, enter a name or email address. The typeahead
   will only include users who aren't already subscribed to the stream.

1. Click **Add**.

{end_tabs}

## Remove users from a stream

{!admin-only.md!}

Anyone can always [unsubscribe themselves from a stream](/help/unsubscribe-from-a-stream).

Organization administrators can also unsubscribe *other* users from any stream,
including streams the admin is not subscribed to.

{start_tabs}

{relative|stream|all}

1. Select a stream.

1. Under **Subscribers**, find the user you would like to remove.

1. Click the **Unsubscribe** button in that row.

{end_tabs}

[configure-invites]: /help/configure-who-can-invite-to-streams

### From a user's profile (alternate method)

This method is useful if you need to remove one user from multiple streams.

{start_tabs}

1. Hover over a user's name in the right sidebar.

1. Click on the ellipsis (<i class="zulip-icon zulip-icon-ellipsis-v-solid"></i>) to
   the right of their name.

1. Click **View full profile**.

1. Select the **Streams** tab.

1. Under **Subscribed streams**, find the stream you would like
   to remove the user from.

1. Click the **Unsubscribe** button in that row.

{end_tabs}
