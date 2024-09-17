# Zulip Pabbly integration

Pabbly Connect supports integrations with more than [2,000+ applications][1].
Get notifications from your Pabbly workflow to Zulip!

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your Pabbly **Dashboard** or **Workflows** menu and create a
  new **workflow** or select an existing one.

1. Configure the **Trigger** event(s) for the workflow. This will be
  the integration app(s) that you'd like to connect with Zulip through
  Pabbly.

1. To configure the **Action** event, select **API (Pabbly)** in the
  **Choose App** section, select **Execute API Request** as **Action Event**
  , and click **Connect**.

1. Once connected, set **Action Event Method** to **POST**, set
  **API Endpoint URL** to the URL generated above, set **Payload type** to
  **JSON**, and **Authentication** to **No Auth**.

1. Tick the **Set Parameters** checkbox to configure the payload. This will be
  the information that will be displayed in your Zulip notification.

1. Click **Save & Send Test Request** to make sure the integration
  is working.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/pabbly/001.png)

### Related documentation

- [Pabbly integration documentation][2]

{!webhooks-url-specification.md!}

[1]: https://www.pabbly.com/connect/integrations/
[2]: https://www.pabbly.com/pabbly-connect-documentation-complete-integration-guide/

