# Zulip Confluence Server/Data Center integration

Get Zulip notifications for your Confluence Server or Data Center spaces!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

      Add the following parameters to the URL:

      - `base_url`: The base URL of your Confluence instance (e.g.,
      `https://wiki.example.com`).
      - `token`: A Confluence
      [personal access token](https://confluence.atlassian.com/enterprise/using-personal-access-tokens-1026032365.html)
      with read access.

1. In Confluence, go to **Settings** > **Advanced** > **Webhooks**.
   Click **Create a Webhook**.
   Set **Title** to a name of your choice, such as `Zulip`. Set **URL**
   to the URL constructed above. Select the
   [events](#filtering-incoming-events) you'd like to be notified about,
   and click **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/confluence/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [Confluence Server webhook guide](https://developer.atlassian.com/server/confluence/confluence-server-webhooks/)
- [Personal access tokens](https://confluence.atlassian.com/enterprise/using-personal-access-tokens-1026032365.html)

{!webhooks-url-specification.md!}
