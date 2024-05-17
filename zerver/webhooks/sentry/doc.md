Get Zulip notifications for the issues in your Sentry projects!

This integration supports Sentry's Node, Python, and Go
[platforms](https://sentry.io/platforms/).  [Contact
us](/help/contact-support) if a platform you care about is missing.

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

    The default topic, if not set in the URL, will be the title of the
    issue or event.

1. In Sentry, go to your organization's **Settings**, and then go to
    **Developer Settings**. Click on the **Create New Integration** button,
    and select **Internal Integration**. Set the **Webhook URL** to the URL
    you constructed in the above step, and then enable **Alert Rule
    Action**.

    You can fill out the remaining details as you like. If you want
    notifications for issues and not just events, you can scroll down to
    **Webhooks** on the same page, and check the box that says **issue**.
    Make sure that you set up the permissions so that the integration will
    be visible to the right people.

    !!! warn ""

        **Note:** Zulip also supports configuring this as a webhook in
        Sentry &mdash; which, while easier to configure (navigate to
        **Settings &gt; Integrations &gt; WebHooks**), may not include the
        full breadth of event types. For instance, some events, like issue
        assignments or issues being resolved, will not trigger notifications
        with this configuration.

1. Once you've saved the internal integration, go to **Alerts** and click
    on the **Create Alert** button to create a new alert rule. Select the
    project for which you want to receive notifications. Set the conditions
    to be whatever you want (e.g. the events you want to be notified for),
    and under **PERFORM THESE ACTIONS**, select **Add an action...** &gt;
    **Send a notification via an integration**, and set it to the internal
    integration you created in the previous step.

{!congrats.md!}

![](/static/images/integrations/sentry/001.png)
![](/static/images/integrations/sentry/002.png)
