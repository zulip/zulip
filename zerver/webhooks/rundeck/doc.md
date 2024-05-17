Receive Job Notifications in Zulip!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. Go to your Rundeck web interface and click on the desired job.
   Click on **Actions** and then select **Edit this Job...**.
   Go to the **Notifications** tab.

1. Next to the desired event, click **Add Notification**. Select
   **Send Webhook** as the Notification Type. Enter the URL constructed
   above. Ensure payload format is **JSON** and Method is **POST**.
   Click **Save**.

{!congrats.md!}

![Rundeck Integration](/static/images/integrations/rundeck/001.png)
