# Zulip Ansible Tower integration

Get Ansible Tower notifications in Zulip!

{start_tabs}

 1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to **Notifications** in your Ansible Tower or AWX Admin Portal,
   and select **Add**.

1. Set **Name** to a name of your choice, such as `Zulip`. Select the
   organization you'd like to be notified about, and set **Type** to
   **Webhook**. Set **Target URL** to the URL generated above, and
   click **Save**.

1. Go to **Organizations**, and find the organization you selected
   when adding the webhook notification. Click the pencil icon to edit
   the organization.

1. Select **Notifications**, and then select the events you would like
   to be notified about, and click **Save**.

{end_tabs}

 {!congrats.md!}

 ![](/static/images/integrations/ansibletower/001.png)

### Related documentation

{!webhooks-url-specification.md!}
