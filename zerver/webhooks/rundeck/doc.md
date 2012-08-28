# Zulip Rundeck integration

Receive Rundeck job notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your Rundeck web interface, and click on the desired job.
   Click on **Actions**, and select **Edit this Job**.

1. Go to the **Notifications** tab. Next to the desired event, click
   **Add Notification**.

1. Select **Send Webhook** as the Notification Type. Enter the URL
   generated above. Ensure payload format is **JSON**, and the method is
   **POST**. Click **Save**.

{end_tabs}

{!congrats.md!}

![Rundeck Integration](/static/images/integrations/rundeck/001.png)

### Related documentation

{!webhooks-url-specification.md!}
