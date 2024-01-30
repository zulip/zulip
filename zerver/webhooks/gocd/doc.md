Zulip supports integration with GoCD and can notify you of
your build statuses.

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. Download the [Webhook generic notification plugin](https://github.com/getsentry/gocd-webhook-notification-plugin/releases) (for plugin installation instructions refer [GoCD's documentation](https://docs.gocd.org/current/extension_points/plugin_user_guide.html#installing-and-uninstalling-of-plugins).)

1. Go to **Admin>Server Configuration>Plugins** in your GoCD project. Click on the gear icon beside the Webhook Notifier Plugin, paste the generated URL and click **Save**.

![](/static/images/integrations/gocd/003.png)

![](/static/images/integrations/gocd/002.png)


{!congrats.md!}

![](/static/images/integrations/gocd/001.png)
