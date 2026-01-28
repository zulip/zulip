# Zulip Notion integration

Get Notion notifications in Zulip!

![](/static/images/integrations/notion/001.png)

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In Notion, go to **Settings & members** > **My connections** >
   **Develop or manage integrations**. Click **Create new integration**.

1. Give your integration a name (e.g., "Zulip"), select the workspace,
   and click **Submit**. Copy the **Internal Integration Secret**.

1. Go to **Settings & members** > **Manage webhooks**. Click
   **Create new webhook**.

1. Set **Target URL** to the URL generated above. Select the
   [events](#filtering-incoming-events) you'd like to be notified about,
   and click **Create**.

{end_tabs}

{!congrats.md!}

{!event-filtering-additional-feature.md!}

### Configuration options

- **Notion API integration token**: Provide your Notion integration
  secret to display page and database titles instead of IDs.

- **Map pages to topics**: When enabled, notifications are routed to
  separate topics based on the entity (e.g., `page: Project Plan`).

### Related documentation

- [Notion Webhooks documentation][notion-webhooks]

{!webhooks-url-specification.md!}

[notion-webhooks]: https://developers.notion.com/docs/webhooks
