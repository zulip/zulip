# Mobile notifications

Zulip can be configured to send [mobile](/help/mobile-app-install-guide)
notifications for [DMs, mentions, and
alerts](/help/dm-mention-alert-notifications), as well as [channel
messages](/help/channel-notifications) and [followed
topics](/help/follow-a-topic#configure-notifications-for-followed-topics).

{start_tabs}

{tab|desktop-web}

{settings_tab|notifications}

1. Toggle the checkboxes in the **Mobile** column of the **Notification
   triggers** table.

{end_tabs}

[notifications-wildcard-mentions]: /help/dm-mention-alert-notifications#wildcard-mentions

## End-to-end encryption (E2EE) for mobile push notifications

Zulip Server 11.0+ and Zulip Cloud support end-to-end encryption for mobile push
notifications. Support is [coming soon][e2ee-flutter-issue] to the Zulip mobile
app. Once implemented, all push notifications sent from an up-to-date version of
the server to an updated version of the app will be end-to-end encrypted.

[e2ee-flutter-issue]: https://github.com/zulip/zulip-flutter/issues/1764

Organization administrators can require end-to-end encryption for
message content in mobile push notifications. When this setting is
enabled, message content will be omitted when sending notifications to
an app that doesn't support end-to-end encryption. Users will see “New
message” in place of message text. See [technical
documentation](https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html#security-and-privacy)
for details.

### Require end-to-end encryption for mobile push notifications

{!admin-only.md!}

{start_tabs}

{settings_tab|organization-settings}

1. Under **Notifications security**, toggle
   **Require end-to-end encryption for push notification content**.

{end_tabs}

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

## Related articles

* [Mobile app installation guides](/help/mobile-app-install-guide)
* [Channel notifications](/help/channel-notifications)
* [DMs, mentions, and alerts](/help/dm-mention-alert-notifications)
* [Email notifications](/help/email-notifications)
* [Desktop notifications](/help/desktop-notifications)
* [Do not disturb](/help/do-not-disturb)
* [Hide message content in emails](/help/hide-message-content-in-emails)
