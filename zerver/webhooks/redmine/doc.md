# Zulip Redmine integration

Get Redmine notifications in Zulip!

!!! warn ""

    **Note**: This integration requires the `redmine_webhook` plugin to be
    installed on your Redmine server. The plugin sends webhook notifications
    to Zulip when issues are created, updated, or other events occur.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Install the `redmine_webhook` plugin on your Redmine server. You can
   find installation instructions at the
   [redmine_webhook](https://github.com/suer/redmine_webhook) GitHub repository.

1. In your Redmine installation, go to **Projects** and select the project
   you want to receive notifications for.

1. On the project main page, enable the **Webhooks** checkbox to activate
   webhook functionality for this project.

1. Click on **Settings** for that project, then navigate to the **WebHook** tab.

1. Add the URL generated above and select the
   [events](#filtering-incoming-events) you'd like to be notified about,
   such as **Issues** → **opened**, **updated**. Save your webhook configuration.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/redmine/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [redmine_webhook plugin documentation](https://github.com/suer/redmine_webhook)

- [Redmine's plugin installation guide](https://www.redmine.org/projects/redmine/wiki/Plugins)

{!webhooks-url-specification.md!}
