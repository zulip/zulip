Get Ansible Tower notifications in Zulip!

 1. {!create-channel.md!}

 1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

 1. Go to your Ansible Tower or AWX Admin Portal. Click **Notifications** on
    the left sidebar, and click **Add**.

 1. Set **Name** to a name of your choice, such as `Zulip`. Select the organization
    you'd like to be notified about, and set **Type** to **Webhook**. Set
    **Target URL** to the URL constructed above, and click **Save**.

 1. Click on **Organizations** on the left sidebar. Click the pencil icon to
    edit the organization you selected above, and click **Notifications**.
    Select the events you would like to be notified about, and click **Save**.

 {!congrats.md!}

 ![](/static/images/integrations/ansibletower/001.png)
