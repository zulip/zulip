# Zulip Redmine integration

Get notifications for Redmine issues in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Install the [`redmine_webhook` plugin](https://github.com/suer/redmine_webhook)
   on your Redmine server.

1. In your Redmine installation, go to **Projects** and select the project
   you want to receive notifications for.

1. From the project page, enable the **Webhooks** checkbox to
   activate webhook functionality. Click on **Settings**, and navigate to
   the **WebHook** tab.

1. Add the URL generated above, select the
   [events](#filtering-incoming-events) you would like to receive
   notifications for, and save your webhook configuration.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/redmine/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [`redmine_webhook` plugin](https://github.com/suer/redmine_webhook)

- [Redmine's plugin installation guide](https://www.redmine.org/projects/redmine/wiki/Plugins)

{!webhooks-url-specification.md!}
