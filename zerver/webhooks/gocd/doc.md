# Zulip GoCD integration

Get GoCD notifications in Zulip!

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Download and install version **v0.0.6** of Sentry's [**WebHook Notifier
   plugin**][1]. Please note that newer versions might not work properly.

1. In your GoCD server, go to **Admin > Server Configuration > Plugins**.
   Click on the gear icon beside the **WebHook Notifier plugin** you just
   installed, paste the generated URL, and click **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/gocd/001.png)

### Related Branches

- [GoCD plugins documentation][2]

{!webhooks-url-specification.md!}

[1]: https://github.com/getsentry/gocd-webhook-notification-plugin/releases/tag/v0.0.6
[2]: https://docs.gocd.org/current/extension_points/plugin_user_guide.html#installing-and-uninstalling-of-plugins
