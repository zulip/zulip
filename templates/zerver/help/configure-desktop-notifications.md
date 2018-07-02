# Configure desktop notifications

You can receive desktop notifications in the corner of your main monitor for
messages sent while Zulip is offscreen.

## Stream messages

To add desktop notifications for a single stream, follow the instructions
[here](/help/set-notifications-for-a-single-stream).

You can also add desktop notifications for all your current streams, or set
a default configuration for streams you join in the future.

{settings_tab|notifications}

1. Under **Stream Messages**, select **Visual desktop notifications** and/or
**Audible desktop notifications**.

1. Under **Apply this change to all current stream subscriptions**, select
"yes" to start receiving desktop notifications for streams that you are
currently subscribed to. Note that this change will apply to all streams even if you
previously set notification preferences for individual streams. Select "no"
if you only want to apply your setting to streams that you subscribe to in
the future.

## Private Messages and @-Mentions

{settings_tab|notifications}

2. Under **Private messages and @-mentions**, select **Visual desktop notifications**
and/or **Audible desktop notifications**.

## Troubleshooting

You may need to adjust your browser or system notification settings in order
to allow Zulip to send you desktop notifications.

### Zulip Desktop app on Mac OS

1. From your desktop, open **System Preferences** and select **Notifications**.

2. Select **Zulip** from the list of apps.

3. Configure the notification style that you would like Zulip to use.

### Zulip Desktop app on Windows

1. Click the **Start** button and select **Settings**. Select **System**,
   and then **Notifications & actions**.

2. Select **Zulip** from the list of apps.

3. Configure the notification style that you would like Zulip to use.

### Firefox

1. With the Firefox browser open, open the **Edit** menu. Select **Preferences**.

2. On the left, select **Privacy & Security**. Scroll to the **Permissions**
   section and select the **Settings** button next to **Notifications**.

3. Find the URL for your Zulip organization, and adjust the **Status**
   selector to **Allow**.

### Chrome

1. With the Chrome browser open, open the **Edit** menu. Select
   **Preferences**.

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
