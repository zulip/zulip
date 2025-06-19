# Mobile notifications

You can customize whether [channel messages](/help/channel-notifications),
[direct messages](/help/dm-mention-alert-notifications) and
[mentions][notifications-wildcard-mentions] trigger notifications in Zulip's
[Android](https://zulip.com/apps/ios) and [iOS](https://zulip.com/apps/ios)
apps.

{start_tabs}

{tab|desktop-web}

{settings_tab|notifications}

1. Toggle the checkboxes for **Channels** and **DMs, mentions, and alerts**
   in the **Mobile** column of the **Notification triggers** table.

{end_tabs}

[notifications-wildcard-mentions]: /help/dm-mention-alert-notifications#wildcard-mentions

## Mobile notifications while online

You can customize whether or not Zulip will send mobile push
notifications while you are actively using one of the Zulip apps.

{start_tabs}

{tab|desktop-web}

{settings_tab|notifications}

1. Under **Mobile message notifications**, toggle
   **Send mobile notifications even if I'm online**, as desired.

{end_tabs}

## Testing mobile notifications

Start by configuring your notifications settings to make it easy to trigger a
notification.

{start_tabs}

{tab|desktop-web}

{settings_tab|notifications}

1. In the **Mobile** column of the **Notification triggers** table, make sure
   the **DMs, mentions, and alerts** checkbox is checked.

1. Under **Mobile message notifications**, make sure the **Send mobile
   notifications even if I'm online** checkbox is checked.

{end_tabs}

Next, test Zulip push notifications on your mobile device.

{start_tabs}

{tab|mobile}

1. [Download](https://zulip.com/apps/) and install the Zulip mobile app if you
   have not done so already.

1. If your Zulip organization is self-hosted (not at `*.zulipchat.com`),
   [check](/help/mobile-notifications#enabling-push-notifications-for-self-hosted-servers)
   whether push notifications have been set up. If they were set up recently,
   you will need to [log out](/help/logging-out) of your account.

1. [Log in](/help/logging-in) to the account you want to test.

1. Ask *another* user (not yourself) to [send you a direct
   message](/help/starting-a-new-direct-message). You should see a Zulip message
   notification in the **notifications area** on your device.

{end_tabs}

## Troubleshooting mobile notifications

### Checking your device settings

Some Android vendors have added extra device-level settings that can impact the
delivery of mobile notifications to apps like Zulip. If you're having issues
with Zulip notifications on your Android phone, we recommend Signal's excellent
[troubleshooting guide](https://support.signal.org/hc/en-us/articles/360007318711-Troubleshooting-Notifications#android_notifications_troubleshooting),
which explains the notification settings for many popular Android vendors.

Android users using microG: we have heard reports of notifications working
if microG's "Cloud Messaging" setting is enabled.

### Enabling push notifications for self-hosted servers

!!! warn ""

    These instructions do not apply to Zulip Cloud organizations (`*.zulipchat.com`).

To enable push notifications for your organization:

{start_tabs}

1. Your server administrator needs to register your Zulip server with the
   [Zulip Mobile Push Notification
   Service](https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html).

1. For organizations with more than 10 users, an
   [owner](/help/user-roles) or billing administrator needs to sign
   up for a [plan](https://zulip.com/plans/#self-hosted) for your organization.

{end_tabs}

### Why am I seeing “New message” in place of message text?

Administrators of self-hosted Zulip servers can
[configure](https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html#security-and-privacy)
push notifications not to include any message content.

## Related articles

* [Channel notifications](/help/channel-notifications)
* [DMs, mentions, and alerts](/help/dm-mention-alert-notifications)
* [Email notifications](/help/email-notifications)
* [Desktop notifications](/help/desktop-notifications)
* [Do not disturb](/help/do-not-disturb)
