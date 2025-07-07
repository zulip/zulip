# Channel notifications

You can configure desktop, mobile, and email notifications on a channel by
channel basis.

## Configure notifications for a single channel

These settings will override any default channel notification settings. In [muted
channels](/help/mute-a-channel), channel notification settings apply only to
[unmuted topics](/help/mute-a-topic).

{start_tabs}

{tab|via-channel-settings}

{!channel-actions.md!}

1. Click **Channel settings**.

{!select-channel-view-personal.md!}

1. Under **Notification settings**, toggle your preferred
   notifications settings for the channel.

{tab|via-personal-settings}

{settings_tab|notifications}

1. In the **Notification triggers** table, find the name of the channel
   you want to configure. If the channel is currently set to the default
   channel notification settings, you can select it from the **Customize
   another channel** dropdown at the bottom of the table.

1. Toggle your preferred notifications settings for the selected
   channel.

!!! tip ""

    To reset a channel's notifications to the default settings, hover
    over its name in the notification triggers table, and click the
    **reset to default notifications**
    (<i class="zulip-icon zulip-icon-reset"></i>) icon.

{tab|mobile}

Access this feature by following the web app instructions in your
mobile device browser.

Implementation of this feature in the mobile app is tracked [on
GitHub](https://github.com/zulip/zulip-flutter/issues/1223). If
you're interested in this feature, please react to the issue's
description with 👍.

{end_tabs}

## Configure default notifications for all channels

These settings only apply to channels where you have not
explicitly set a notification preference.

{start_tabs}

{tab|desktop-web}

{settings_tab|notifications}

1. In the **Notification triggers** table,
   toggle the settings for **Channels**.

{tab|mobile}

Access this feature by following the web app instructions in your
mobile device browser.

Implementation of this feature in the mobile app is tracked [on
GitHub](https://github.com/zulip/zulip-flutter/issues/661). If
you're interested in this feature, please react to the issue's
description with 👍.

{end_tabs}

## Related articles

* [Desktop notifications](/help/desktop-notifications)
* [Email notifications](/help/email-notifications)
* [Mobile notifications](/help/mobile-notifications)
* [Mute or unmute a channel](/help/mute-a-channel)
* [Mute or unmute a topic](/help/mute-a-topic)
* [DMs, mentions, and alerts](/help/dm-mention-alert-notifications)
* [Do not disturb](/help/do-not-disturb)
