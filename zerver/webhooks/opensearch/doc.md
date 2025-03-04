# Zulip OpenSearch integration

Get notifications from OpenSearch in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Append `&topic=topic+name`
   to the URL generated above, where `topic+name` is the
   URL-encoded name of the topic you want to use.

1. In OpenSearch, click the **gear** (<i class="fa fa-cog"></i>) icon in the
   bottom-left corner. Click on **Settings and setup**. In the sidebar,
   click on **Channels** under **Notification channels**. Click **Create
   channel**.
   You should see a screen like this:
   ![Create channel](/static/images/integrations/opensearch/002.png)

1. Fill in the channel name and description. For **Channel type**, select
   **Custom webhook**. The **Method** should be **POST**, and the **Define
   endpoints by** option should be **Webhook URL**. Paste the URL generated
    and updated above into the **Webhook URL** field.

1. Click **Send test message**. A test message should
   appear in Zulip. Save the channel by selecting **Create**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/opensearch/001.png)

### Related documentation

{!webhooks-url-specification.md!}
