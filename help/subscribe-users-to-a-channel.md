# Subscribe users to a channel

Organization [administrators](/help/user-roles) can
[configure](/help/configure-who-can-invite-to-channels#configure-who-can-subscribe-others-to-channels-in-general)
who can subscribe other users to channels. Channel administrators can
configure who can
[subscribe](/help/configure-who-can-invite-to-channels#configure-who-can-subscribe-anyone-to-a-specific-channel)
anyone to a particular channel.

You will only see the options below if you have the required permissions.

## Subscribe users to a channel

{start_tabs}

{tab|desktop-web}

{relative|channel|all}

1. Select a channel.

{!select-channel-view-subscribers.md!}

1. Under **Add subscribers**, enter a name or email address. The typeahead
   will only include users who aren't already subscribed to the channel.

1. Configure **Send notification message to newly subscribed users** as desired.

1. Click **Add**.

!!! tip ""

      To subscribe users in bulk, you can copy members from an
      existing channel or [user group](/help/user-groups).

{tab|mobile}

Access this feature by following the web app instructions in your
mobile device browser.

Implementation of this feature in the mobile app is tracked [on
GitHub](https://github.com/zulip/zulip-flutter/issues/1222). If
you're interested in this feature, please react to the issue's
description with 👍.

{end_tabs}

{!automated-dm-channel-subscription.md!}

## Alternate methods to subscribe users to a channel

### Via channel settings

{start_tabs}

{tab|desktop-web}

{!channel-actions.md!}

1. Click **Channel settings**.

{!select-channel-view-subscribers.md!}

1. Under **Add subscribers**, enter a name or email address. The typeahead
   will only include users who aren't already subscribed to the channel.

1. Configure **Send notification message to newly subscribed users** as desired.

1. Click **Add**.

{end_tabs}

### Via mentioning a user in the compose box

When you [mention a user](/help/mention-a-user-or-group) while composing
a message in the web or desktop app, an alert banner appears above the
compose box if they are not subscribed to the channel.

Click the **Subscribe them** button on the banner to subscribe the user to
the channel. You will not see the button if you don't have permission to
subscribe the user.

!!! tip ""

      You do not have to send the message you are composing for
      the user to be subscribed this way.

## Related articles

* [Introduction to channels](/help/introduction-to-channels)
* [Unsubscribe users from a channel](/help/unsubscribe-users-from-a-channel)
* [Manage a user's channel subscriptions](/help/manage-user-channel-subscriptions)
* [Configure who can subscribe other users to channels](/help/configure-who-can-invite-to-channels)
* [Set default channels for new users](/help/set-default-channels-for-new-users)
* [User roles](/help/user-roles)
* [Mention a user or group](/help/mention-a-user-or-group)
* [View channel subscribers](/help/view-channel-subscribers)
