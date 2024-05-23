# Add or remove users from a channel

By default, anyone (other than guests) subscribed to a channel can add
users to that channel. Additionally, anyone (other than guests) can add
users to a public channel, whether or not they are subscribed to the
channel. Anyone can always [unsubscribe themselves from a channel][unsubscribe].

Organization administrators can also unsubscribe *other* users from any channel,
including channels the admin is not subscribed to. They can also configure which
[roles](/help/roles-and-permissions) have access to [add other users to a
channel][add-users] or [remove other users from a channel][remove-users].

[add-users]: /help/configure-who-can-invite-to-channels#configure-who-can-add-users
[remove-users]: /help/configure-who-can-invite-to-channels#configure-who-can-remove-users

## Add users to a channel

{start_tabs}

{tab|desktop-web}

{relative|channel|all}

1. Select a channel.

{!select-channel-view-subscribers.md!}

1. Under **Add subscribers**, enter a name or email address. The typeahead
   will only include users who aren't already subscribed to the channel.

1. Click **Add**.

!!! tip ""

      To add users in bulk, you can copy members from an
      existing channel or [user group](/help/user-groups).

{tab|mobile}

{!mobile-all-channels-view.md!}

{!channel-long-press-menu.md!}

1. Tap **Channel settings**.

1. Tap **Add subscribers**.

1. Start typing the name of the person you want to add, and
   select their name from the list of suggestions. You can continue
   adding as many users as you like.

1. Approve by tapping the **checkmark**
   (<img src="/static/images/help/mobile-check-circle-icon.svg" alt="checkmark" class="help-center-icon"/>)
   button in the bottom right corner of the app.

{end_tabs}

{!automated-dm-channel-subscription.md!}

## Alternate methods to add users to a channel

### Via channel settings

{start_tabs}

{tab|desktop-web}

{!channel-actions.md!}

1. Click **Channel settings**.

{!select-channel-view-subscribers.md!}

1. Under **Add subscribers**, enter a name or email address. The typeahead
   will only include users who aren't already subscribed to the channel.

1. Click **Add**.

{tab|mobile}

{!channel-long-press-menu.md!}

1. Tap **Channel settings**.

1. Tap **Add subscribers**.

1. Start typing the name of the person you want to add, and
   select their name from the list of suggestions. You can continue
   adding as many users as you like.

1. Approve by tapping the **checkmark**
   (<img src="/static/images/help/mobile-check-circle-icon.svg" alt="checkmark" class="help-center-icon"/>)
   button in the bottom right corner of the app.

{!mobile-channel-settings-menu-tip.md!}

{end_tabs}

### Via mentioning a user in the compose box

When you [mention a user](/help/mention-a-user-or-group) while composing
a message in the web or desktop app, an alert banner appears above the
compose box if they are not subscribed to the channel.

Click the **Subscribe them** button on the banner to add the user to the
channel. You will not see the button if you don't have permission to
subscribe the user.

!!! tip ""

      You do not have to send the message you are composing for
      the user to be subscribed this way.

## Remove users from a channel

{start_tabs}

{tab|desktop-web}

{relative|channel|all}

1. Select a channel.

{!select-channel-view-subscribers.md!}

1. Under **Subscribers**, find the user you would like to remove.

1. Click the **Unsubscribe** button in that row.

{!channel-menu-subscribers-tab-tip.md!}

{tab|via-right-sidebar}

{!right-sidebar-view-profile.md!}

1. Select the **Channels** tab.

1. Under **Subscribed channels**, find the channel you would like
   to remove the user from.

1. Click the **Unsubscribe** button in that row.

!!! tip ""

    This method is useful if you need to remove one user from multiple channels.

{end_tabs}

## Related articles

* [Introduction to channels](/help/introduction-to-channels)
* [Unsubscribe from a channel][unsubscribe]
* [Manage a user's channel subscriptions](/help/manage-user-channel-subscriptions)
* [Restrict channel invitations](/help/configure-who-can-invite-to-channels)
* [Set default channels for new users](/help/set-default-channels-for-new-users)
* [Roles and permissions](/help/roles-and-permissions)
* [Mention a user or group](/help/mention-a-user-or-group)
* [View channel subscribers](/help/view-channel-subscribers)

[unsubscribe]: /help/unsubscribe-from-a-channel
