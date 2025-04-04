# Zulip Taiga integration

Receive Zulip notifications for your Taiga projects!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your **Projects Dashboard** on Taiga, and select the project you'd like to
   receive notifications for.

1. Go to **Admin**, and select  **Integrations**. Click **Add a new webhook**.

1. Set **Name** to a name of your choice, such as `Zulip`. Set **URL** to the
   URL generated above, and set **Secret key** to the API key of the bot created
   above. Save the form.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/taiga/001.png)

### Related documentation

{!webhooks-url-specification.md!}
