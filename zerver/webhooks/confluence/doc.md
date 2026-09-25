# Zulip Confluence Server/Data Center integration

Get Zulip notifications for your Confluence Server or Data Center spaces!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

      When prompted for **Personal access token**, paste a Confluence
      [personal access token](https://confluence.atlassian.com/enterprise/using-personal-access-tokens-1026032365.html)
      with read access. The token is stored as bot configuration and is
      not included in the webhook URL.

1. {!generate-webhook-url-basic.md!}

      Add the following parameter to the URL:

      - `base_url`: The base URL of your Confluence instance (e.g.,
      `https://wiki.example.com`).

1. In Confluence, go to **Administration** > **General Configuration** > **Webhooks**.
   Click **Create a Webhook**.
   Set **Name** to a name of your choice, such as `Zulip`. Set **URL**
   to the URL constructed above. Select the
   [events](#filtering-incoming-events) you'd like to be notified about,
   and click **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/confluence/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [Confluence Server webhook guide](https://confluence.atlassian.com/doc/managing-webhooks-1021225606.html)
- [Personal access tokens](https://confluence.atlassian.com/enterprise/using-personal-access-tokens-1026032365.html)

{!webhooks-url-specification.md!}
