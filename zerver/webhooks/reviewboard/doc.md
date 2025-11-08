# Zulip Review Board integration

Get Review Board notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. On your Review Board **Dashboard**, click your team's name in the top-right
   corner, and click **Team administration**. Select **WebHooks** on the
   left sidebar, and click **+ Create a WebHook**.

1. Make sure the **Enabled** option is checked. Set **URL** to the URL generated
   above, and select the [events](#filtering-incoming-events) you'd like to
   be notified about. Set **Encoding** to **JSON**, and click **Create WebHook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/reviewboard/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
