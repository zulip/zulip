# Zulip Sentry integration

Get Zulip notifications for the issues in your Sentry projects!

!!! warn ""

    **Note:** This integration supports Sentry's Node, Python, and Go
    [platforms](https://sentry.io/platforms/). If there's a platform
    you're interested in seeing support for that's missing, let us
    know in the [integrations][dev-community] channel of the Zulip
    development community.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In your Sentry organization's **Settings**, go to **Developer
   Settings**. Click on **Create New Integration**, and select
   **Internal Integration**.

    !!! warn ""

        **Note**: Zulip also supports configuring this integration as a
        webhook in Sentry. While this is easier to configure (navigate
        to **Settings &gt; Integrations**, and search for **WebHooks**),
        it doesn't support the full breadth of event types. For instance,
        some events, like issue assignments or issues being resolved,
        will not trigger notifications with this configuration.

1. Set the **Webhook URL** to the URL generated above, and then enable
   **Alert Rule Action**. Fill out the remaining details based on your
   preferences, and click **Save Changes**.

    !!! tip ""

        If you want notifications for issues, as well as events, you can
        scroll down to **Webhooks** on the same page, and toggle the
        **issue** checkbox.

1. Go to **Alerts**, and click **Create Alert**.

1. Select the project for which you want to receive notifications, and
   set the conditions as you'd prefer (e.g., the events you want to be
   notified about). Under **PERFORM THESE ACTIONS**, select **Add an
   action...** &gt; **Send a notification via an integration**, and set
   it to the internal integration created above.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/sentry/001.png)

### Related documentation

{!webhooks-url-specification.md!}

[dev-community]: https://chat.zulip.org/#narrow/channel/127-integrations
