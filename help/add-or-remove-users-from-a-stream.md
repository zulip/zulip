# Add or remove users from a stream

By default, anyone (other than guests) subscribed to a stream can add
users to that stream. Additionally, anyone (other than guests) can add
users to a public stream, whether or not they are subscribed to the
stream. Anyone can always [unsubscribe themselves from a stream](/help/unsubscribe-from-a-stream).

Organization administrators can also unsubscribe *other* users from any stream,
including streams the admin is not subscribed to. They can also configure which
[roles](/help/roles-and-permissions) have access to [add other users to a
stream][add-users] or [remove other users from a stream][remove-users].

[add-users]: /help/configure-who-can-invite-to-streams#configure-who-can-add-users
[remove-users]: /help/configure-who-can-invite-to-streams#configure-who-can-remove-users

## Add users to a stream

{start_tabs}

{tab|desktop-web}

{relative|stream|all}

1. Select a stream.

{!select-stream-view-subscribers.md!}

1. Under **Add subscribers**, enter a name or email address. The typeahead
   will only include users who aren't already subscribed to the stream.

1. Click **Add**.

!!! tip ""

      To add users in bulk, you can copy members from an
      existing stream or [user group](/help/user-groups).

{tab|mobile}

{!mobile-all-streams-view.md!}

{!stream-long-press-menu.md!}

1. Tap **Stream settings**.

1. Tap **Add subscribers**.

1. Start typing the name of the person you want to add, and
   select their name from the list of suggestions. You can continue
   adding as many users as you like.

1. Approve by tapping the **checkmark**
   (<img src="/static/images/help/mobile-check-circle-icon.svg" alt="checkmark" class="mobile-icon"/>)
   button in the bottom right corner of the app.

{end_tabs}

{!automated-dm-stream-subscription.md!}

## Alternate methods to add users to a stream

### Via stream settings

{start_tabs}

{tab|desktop-web}

{!stream-actions.md!}

1. Click **Stream settings**.

{!select-stream-view-subscribers.md!}

1. Under **Add subscribers**, enter a name or email address. The typeahead
   will only include users who aren't already subscribed to the stream.

1. Click **Add**.

{tab|mobile}

{!stream-long-press-menu.md!}

1. Tap **Stream settings**.

1. Tap **Add subscribers**.

1. Start typing the name of the person you want to add, and
   select their name from the list of suggestions. You can continue
   adding as many users as you like.

1. Approve by tapping the **checkmark**
   (<img src="/static/images/help/mobile-check-circle-icon.svg" alt="checkmark" class="mobile-icon"/>)
   button in the bottom right corner of the app.

{!mobile-stream-settings-menu-tip.md!}

{end_tabs}

### Via mentioning a user in the compose box

When you [mention a user](/help/mention-a-user-or-group) while composing
a message in the web or desktop app, an alert banner appears above the
compose box if they are not subscribed to the stream.

Click the **Subscribe them** button on the banner to add the user to the
stream. You will not see the button if you don't have permission to
subscribe the user.

!!! tip ""

      You do not have to send the message you are composing for
      the user to be subscribed this way.

## Remove users from a stream

{start_tabs}

{tab|desktop-web}

{relative|stream|all}

1. Select a stream.

{!select-stream-view-subscribers.md!}

1. Under **Subscribers**, find the user you would like to remove.

1. Click the **Unsubscribe** button in that row.

!!! tip ""

    You can also hover over a stream in the left sidebar, click on the
    **ellipsis** (<i class="zulip-icon zulip-icon-more-vertical"></i>), and
    select **Stream settings** to access the **Subscribers** tab.

{end_tabs}

## Alternate method to remove users from a stream

This method is useful if you need to remove one user from multiple streams.

{start_tabs}

{tab|desktop-web}

{!right-sidebar-view-profile.md!}

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
