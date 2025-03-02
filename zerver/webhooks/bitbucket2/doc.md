# Zulip Bitbucket integration

Zulip supports both Git and Mercurial notifications from
Bitbucket. This integration is for the new-style Bitbucket
webhooks used by the Bitbucket SAAS service.

For the old-style Bitbucket webhooks used by Bitbucket Enterprise,
click [here](./bitbucket), and for the new-style webhooks used by
Bitbucket Server click [here](./bitbucket3).

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-with-branch-filtering.md!}

1. On your repository's web page, go to **Settings**. Select
   **Webhooks**, and then click **Add webhook**.

1. Set **Title** to a title of your choice, such as `Zulip`. Set **URL**
   to the URL generated above, and toggle the **Active** checkbox.
   Select the **Triggers** you'd like to be notified about, and click
   **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/bitbucket/003.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
