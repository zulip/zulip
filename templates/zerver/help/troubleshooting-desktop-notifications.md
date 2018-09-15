# Troubleshooting desktop notifications

First, make sure you have enabled
[desktop notifications for PMs](/help/pm-mention-alert-notifications) or for the
[stream](/help/stream-notifications) you are testing with.

Desktop notifications are triggered when a message arrives, and Zulip is not
in focus or the message is offscreen. You must have Zulip open in a browser
tab or in the Zulip desktop app to receive desktop notifications.

**Visual desktop notifications** appear in the corner of your main monitor.
**Audible desktop notifications** make a sound.

The most common issue is that your browser or system settings are blocking
notifications from Zulip.

## Desktop app on macOS

1. Open your Mac **System Preferences** and select **Notifications**.

2. Select **Zulip** from the list of apps.

3. Configure the notification style that you would like Zulip to use.

## Desktop app on Windows

1. Click the **Start** button and select **Settings**. Select **System**,
   and then **Notifications & actions**.

2. Select **Zulip** from the list of apps.

3. Configure the notification style that you would like Zulip to use.

## Firefox

1. Open the Firefox **Edit** menu. Select **Preferences**.

2. On the left, select **Privacy & Security**. Scroll to the **Permissions**
   section and select the **Settings** button next to **Notifications**.

3. Find the URL for your Zulip organization, and adjust the **Status**
   selector to **Allow**.

## Chrome

1. Click on **Secure** to the left of the URL bar. It should be green and
   have a lock icon next to it.

1. Set **Notifications** and **Sound** to **Allow**.

Alternate instructions:

1. Open the Chrome **Edit** menu. Select **Preferences**.

2. On the top left, select the menu icon (<i class="fa
   fa-bars"></i>). Select **Advanced**, and then **Privacy & Security**.
   Click on **Content settings** (partway down the page), and select
   **Notifications**.

3. If the Zulip URL for your organization is listed under **Blocked**,
   select the menu icon (<i class="fa fa-ellipsis-v"></i>) to its right, and
   click **Remove**.

4. Next to **Allow**, click **Add**.

5. Paste the Zulip URL for your organization into the site field, and click
    **Add**.
