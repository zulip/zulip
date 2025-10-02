# Zulip Zapier integration

Zapier supports integrations with
[hundreds of popular products](https://zapier.com/apps). Get notifications
sent by Zapier directly in Zulip.

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. Create an account on [Zapier](https://zapier.com). Go to [Zulip
   Integrations][1], and select the app you want to connect to Zulip.

1. Under **Choose a Trigger**, select an event in the app you are
   connecting to Zulip. Under **Choose an Action**, select **Send a
   Private Message** or **Send a Stream Message**. Click **Connect**.

1. Follow the instructions in the right sidebar to set up the trigger
   event.

1. Select the Zulip action in the center panel, and under **Account** in
   the right sidebar, click **Sign in** to connect your bot to Zapier.

1. On the **Allow Zapier to access your Zulip Account** screen, enter
   the URL for your Zulip organization, and the email address and API
   key of the bot you created above.

1. Under **Action** in the right sidebar, configure **Recipients** for
   direct messages, or **Stream name** and **Topic** for channel
   messages. Configure **Message content**.

    !!! tip ""
        To receive notifications as direct messages, if your email
        in Zulip is [configured](/help/configure-email-visibility)
        to be visible to **Admins, moderators, members and guests**,
        enter the email associated with your Zulip account in the
        **Recipients** field. Otherwise, enter `user` +
        [your user ID](/help/view-someones-profile) +
        `@` + your Zulip domain, e.g., `user123@{{ display_host }}`.

1. Click **Publish** to enable your Zap.

{end_tabs}

[1]: https://zapier.com/apps/zulip/integrations
