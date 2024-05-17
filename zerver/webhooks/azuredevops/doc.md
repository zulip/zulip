# Zulip Azure DevOps integration

Get Azure DevOps notifications in Zulip!

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your project on Azure DevOps, click on the **Project
   settings** in the bottom left corner and select **Service
   hooks**. Click on **Create subscription**, select
   **Web hooks**, and click **Next**.

1. Select the [events](#filtering-incoming-events) you would like to receive
   notifications for, and click **Next**.

1. Set **URL** to the URL you generated. Ensure that **Resource
   details to send** and **Detailed messages to send** are set to
   **All**. Click **Finish**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/azuredevops/001.png)

{% if all_event_types is defined %}

{!event-filtering-additional-feature.md!}

{% endif %}

### Configuration options

{!git-branches-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
