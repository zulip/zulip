Get Zulip notifications for the issues in your Sentry projects!

This integration supports Sentry's Node, Python, and Go
[platforms](https://sentry.io/platforms/).  [Contact
us](/help/contact-support) if a platform you care about is missing.

1. {!create-stream.md!}

2. {!create-bot-construct-url-indented.md!}

    The default topic, if not set in the URL, will be the title of the
    issue or event.

3. Go to your organization's **settings** in Sentry. Then go to
**Developer Settings** and click on the button to create a
**New Internal Integration**. There, set the **Webhook URL** to
the URL you constructed in the above step then enable
**Alert Rule Action**. You can fill out the remaining details as
you like. If you want notifications for issues and not just events,
you can scroll down to **Webhooks** on the same page and check the
box that says **issues**. Make sure that you set up the permissions
so that the integration will visible to the right people.

    **NOTE:** Zulip also supports configuring this as a webhook in Sentry
&mdash; which, while easier to configure (Navigate to **Settings > Integrations
> WebHooks**) may not include the full breadth of event types. For instance,
some events, like issue assignments or issues being resolved, will not trigger
notifications with this configuration.

4. Once you've saved the internal integration, go to you're project's
settings (**settings** > **Projects** > Select the project). Once
there go to **Alerts** and click on the **New Alert Rule** button to
create a new alert rule. Set the conditions to be whatever you want
(the events you want to be notified for) and under
**PERFORM THESE ACTIONS** select **Add an action...** >
**Send notification to one legacy integration** and set it to the
internal integration you created in the previous step.

{!congrats.md!}

![](/static/images/integrations/sentry/001.png)
![](/static/images/integrations/sentry/002.png)
