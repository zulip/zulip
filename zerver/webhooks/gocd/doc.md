# Zulip GoCD integration

Get GoCD notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. [Download][1] and [install][2] Sentry's **GoCD WebHook Notification
   plugin**.

    !!! warn ""

        **Note**: the GoCD WebHook Notification plugin will only send
        webhook payloads over HTTPS.

1. In your GoCD server, go to **Admin > Server Configuration > Plugins**,
   and click on the gear icon beside the **GoCD WebHook Notification
   plugin** that you installed.

1. Set **WebHook URL** to the URL generated above, and click **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/gocd/001.png)

### Related Branches

- [GoCD plugin user guide][3]

{!webhooks-url-specification.md!}

[1]: https://github.com/getsentry/gocd-webhook-notification-plugin/releases
[2]: https://docs.gocd.org/current/extension_points/plugin_user_guide.html#installing-and-uninstalling-of-plugins
[3]: https://docs.gocd.org/current/extension_points/plugin_user_guide.html
