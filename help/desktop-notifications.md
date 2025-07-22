# Desktop notifications

Zulip offers visual and audible desktop notifications. You can
customize whether [channel messages](/help/channel-notifications),
[direct messages](/help/dm-mention-alert-notifications) and
[mentions](/help/dm-mention-alert-notifications#wildcard-mentions)
trigger desktop notifications.

{start_tabs}

{settings_tab|notifications}

1. Toggle the checkboxes for **Channels** and **DMs, mentions, and alerts**
   in the **Desktop** column of the **Notification triggers** table.

{end_tabs}

## Notification sound

You can select the sound Zulip uses for audible desktop notifications. Choosing
**None** disables all audible desktop notifications.

### Change notification sound

{start_tabs}

{settings_tab|notifications}

1. Under **Desktop message notifications**, configure
   **Notification sound**.

{end_tabs}

!!! tip ""
    To hear the selected sound, click the <i class="fa fa-play-circle"></i> to the right of your selection.

## Unread count badge

By default, Zulip displays a count of your unmuted unread messages on the
[desktop app](https://zulip.com/apps/) sidebar and on the browser tab icon. You
can configure the badge to only count [direct messages](/help/direct-messages)
and [mentions](/help/mention-a-user-or-group), or to include messages in
[followed topics](/help/follow-a-topic) but not other
[channel](/help/introduction-to-channels) messages.

### Configure unread count badge

{start_tabs}

{settings_tab|notifications}

1. Under **Desktop message notifications**, configure
   **Unread count badge**.

{end_tabs}

### Disable unread count badge

{start_tabs}

{settings_tab|notifications}

1. Under **Desktop message notifications**, select **None** from the
   **Unread count badge** dropdown.

{end_tabs}

## Testing desktop notifications

!!! warn ""

    This does not make an unread count badge appear.

{start_tabs}

{tab|desktop-web}

{settings_tab|notifications}

1. Under **Desktop message notifications**, click **Send a test notification**.
   If notifications are working, you will receive a test notification.

{end_tabs}

## Troubleshooting desktop notifications

Desktop notifications are triggered when a message arrives, and Zulip is not
in focus or the message is offscreen. You must have Zulip open in a browser
tab or in the Zulip desktop app to receive desktop notifications.

**Visual desktop notifications** appear in the corner of your main monitor.
**Audible desktop notifications** make a sound.

To receive notifications in the desktop app, make sure that [Do Not Disturb
mode](/help/do-not-disturb) is turned off.

### Check notification settings for DMs or channels

If you have successfully received a [test
notification](#testing-desktop-notifications), but you aren't seeing desktop
notifications for new messages, check your Zulip notification settings. Make
sure you have enabled desktop notifications [for
DMs](/help/dm-mention-alert-notifications) or [for the
channel](/help/channel-notifications) you are testing. Messages in [muted
topics](/help/mute-a-topic) will not trigger notifications.

### Check platform settings

The most common issue is that your browser or system settings are blocking
notifications from Zulip. Before checking Zulip-specific settings, make sure
that **Do Not Disturb mode** is not enabled on your computer.

{start_tabs}

{tab|chrome}

1. Click on the site information menu to the left of the URL for your Zulip
   organization.

1. Toggle **Notifications** and **Sound**. If you don't see those options,
   click on **Site settings**, and set **Notifications** and **Sound** to
   **Allow**.

Alternate instructions:

1. Select the Chrome menu at the top right of the browser, and select
   **Settings**.

1. Select **Privacy and security**, **Site Settings**, and then
   **Notifications**.

1. Next to **Allowed to send notifications**, select **Add**.

1. Paste the Zulip URL for your organization into the site field, and
   click **Add**.

{tab|firefox}

1. Select the Firefox menu at the top right of the browser, and select
   **Settings**.

1. On the left, select **Privacy & Security**. Scroll to the **Permissions**
   section and select the **Settings** button next to **Notifications**.

1. Find the URL for your Zulip organization, and adjust the **Status**
   selector to **Allow**.

{tab|desktop-app}

**Windows**

1. Click the **Start** button and select **Settings**. Select **System**,
   and then **Notifications & actions**.

1. Select **Zulip** from the list of apps.

1. Configure the notification style that you would like Zulip to use.

**macOS**

1. Open your Mac **System Preferences** and select **Notifications**.

1. Select **Zulip** from the list of apps.

1. Configure the notification style that you would like Zulip to use.

{end_tabs}


## Related articles

* [Channel notifications](/help/channel-notifications)
* [DMs, mentions, and alerts](/help/dm-mention-alert-notifications)
* [Email notifications](/help/email-notifications)
* [Mobile notifications](/help/mobile-notifications)
* [Do not disturb](/help/do-not-disturb)
