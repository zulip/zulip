Get Azure Devops notifications in Zulip!

### Basic setup

{start_tabs}

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your project on Azure DevOps, click on the **Project
   settings** in the bottom left corner and select **Service
   hooks**. Click on **Create subscription**, select
   **Web hooks** and then click **Next**.

1. Select the events you would like to receive notifications for and
   then click **Next**. The events supported by this integration are
   listed below in **Additional features**.

1. Set **URL** to the URL constructed above. Ensure that **Resource
   details to send** and **Detailed messages to send** are set to
   **All**. Click **Finish**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/azuredevops/001.png)

### Additional features

{% if all_event_types is defined %}

{!event-filtering-additional-feature.md!}

{% endif %}

{!git-branches-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
