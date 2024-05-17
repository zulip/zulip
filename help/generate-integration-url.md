# Generate URL for an integration

Many [Zulip integrations](/integrations/) are webhooks. An incoming webhook
integration allows a third-party service, such as an [issue
tracker](/integrations/doc/github) or an [alerting
tool](/integrations/doc/pagerduty), to post updates to Zulip. To configure
where these updates will be posted, you need to generate a special Zulip
integration URL.

{start_tabs}

{tab|via-personal-settings}

{settings_tab|your-bots}

1. Click the **link** (<i class="fa fa-link"></i>) icon on the profile card of
   an **Incoming webhook** bot.

1. Select the desired integration from the **Integration** dropdown.

1. _(optional)_ Select the destination channel from the
   **Where to send notifications** dropdown.

1. _(optional)_ Select **Send all notifications to a single topic**, and
   enter the topic name.

1. _(optional)_ Select **Filter events that will trigger notifications?**,
   and select which supported events should trigger notifications.

1. Click **Copy URL** to add the URL to your clipboard.

!!! tip ""

    You can also click the **pencil** (<i class="fa fa-pencil"></i>) icon,
    scroll down to the bottom, and click **Generate URL for an integration**.

{tab|via-organization-settings}

{!admin-only.md!}

{settings_tab|bot-list-admin}

1. In the **Actions** column, click the **pencil** (<i class="fa fa-pencil"></i>)
   icon for an **Incoming webhook** bot.

1. Scroll down to the bottom, and click **Generate URL for an integration**.

1. Select the desired integration from the **Integration** dropdown.

1. _(optional)_ Select the destination channel from the
   **Where to send notifications** dropdown.

1. _(optional)_ Select **Send all notifications to a single topic**, and
   enter the topic name.

1. _(optional)_ Select **Filter events that will trigger notifications?**,
   and select which supported events should trigger notifications.

1. Click **Copy URL** to add the URL to your clipboard.

{end_tabs}

## Related articles

* [Integrations overview](/help/integrations-overview)
* [Bots overview](/help/bots-overview)
* [Add a bot or integration](/help/add-a-bot-or-integration)
* [View all bots in your organization](/help/view-all-bots-in-your-organization)
* [Request an integration](/help/request-an-integration)
