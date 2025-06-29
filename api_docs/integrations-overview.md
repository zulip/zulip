# Integrations overview

Integrations let you connect Zulip with other products. For example, you can get
notification messages in Zulip when an issue in your tracker is updated, or for
alerts from your monitoring tool.

Zulip offers [over 120 native integrations](/integrations/), which take
advantage of Zulip's [topics](/help/introduction-to-topics) to organize
notification messages. Additionally, thousands of integrations are available
through [Zapier](https://zapier.com/apps) and [IFTTT](https://ifttt.com/search).
You can also [connect any webhook designed to work with
Slack](/integrations/doc/slack_incoming) to Zulip.

If you don't find an integration you need, you can:

- [Write your own integration](#write-your-own-integration). You can [submit a
pull
request](https://zulip.readthedocs.io/en/latest/contributing/reviewable-prs.html)
to get your integration merged into the main Zulip repository.

- [File an issue](https://github.com/zulip/zulip/issues/new/choose) to request
  an integration (if it's a nice-to-have).

- [Contact Zulip Sales](mailto:sales@zulip.com) to inquire about a custom
  development contract.

## Set up an integration

### Native integrations

{start_tabs}

1. [Search Zulip's integrations](/integrations/) for the product you'd like to
   connect to Zulip.

1. Click on the card for the product, and follow the instructions on the page.

{end_tabs}

### Integrate via Zapier or IFTTT

If you don't see a native Zulip integration, you can access thousands of
additional integrations through [Zapier](https://zapier.com/apps) and
[IFTTT](https://ifttt.com/search).

{start_tabs}

1. Search [Zapier](https://zapier.com/apps) or [IFTTT](https://ifttt.com/search)
   for the product you'd like to connect to Zulip.

1. Follow the integration instructions for [Zapier](/integrations/doc/zapier) or
   [IFTTT](/integrations/doc/ifttt).

{end_tabs}

### Integrate via Slack-compatible webhook API

Zulip can process incoming webhook messages written to work with [Slack's
webhook API](https://api.slack.com/messaging/webhooks). This makes it easy to
quickly move your integrations when [migrating your
organization](/help/import-from-slack) from Slack to Zulip, or integrate any
product that has a Slack webhook integration with Zulip .

!!! warn ""

     **Note:** In the long term, the recommended approach is to use
     Zulip's native integrations, which take advantage of Zulip's topics.
     There may also be some quirks when Slack's formatting system is
     translated into Zulip's.

{start_tabs}

1. [Create a bot](/help/add-a-bot-or-integration) for the Slack-compatible
   webhook. Make sure that you select **Incoming webhook** as the **Bot type**.

1. Decide where to send Slack-compatible webhook notifications, and [generate
   the integration URL](https://zulip.com/help/generate-integration-url).

1. Use the generated URL anywhere you would use a Slack webhook.

{end_tabs}

### Integrate via email

If the product you'd like to integrate can send email notifications, you can
[send those emails to a Zulip channel](/help/message-a-channel-by-email). The
email subject will become the Zulip topic, and the email body will become the
Zulip message.

For example, you can configure your personal GitHub notifications to go to a
Zulip channel rather than your email inbox. Notifications for each issue or pull
request will be grouped into a single topic.

## Write your own integration

You can write your own Zulip integrations using the well-documented APIs below.
For example, if your company develops software, you can create a custom
integration to connect your product to Zulip.

If you need help, best-effort community support is available in the [Zulip
development community](https://zulip.com/development-community/). To inquire
about options for custom development, [contact Zulip
Sales](mailto:sales@zulip.com).

### Sending content into Zulip

* If the third-party service supports outgoing webhooks, you likely want to
  build an [incoming webhook integration](/api/incoming-webhooks-overview).

* If it doesn't, you may want to write a
  [script or plugin integration](/api/non-webhook-integrations).

* The [`zulip-send` tool](/api/send-message) makes it easy to send Zulip
  messages from shell scripts.

* Finally, you can
  [send messages using Zulip's API](/api/send-message), with bindings for
  Python, JavaScript and [other languages](/api/client-libraries).

### Sending and receiving content

* To react to activity inside Zulip, look at Zulip's
  [Python framework for interactive bots](/api/running-bots) or
  [Zulip's real-time events API](/api/get-events).

* If what you want isn't covered by the above, check out the full
  [REST API](/api/rest). The web, mobile, desktop, and terminal apps are
  built on top of this API, so it can do anything a human user can do. Most
  but not all of the endpoints are documented on this site; if you need
  something that isn't there check out Zulip's
  [REST endpoints](https://github.com/zulip/zulip/blob/main/zproject/urls.py).

## Related articles

* [Bots overview](/help/bots-overview)
* [Set up integrations](/help/set-up-integrations)
* [Add a bot or integration](/help/add-a-bot-or-integration)
* [Generate integration URL](/help/generate-integration-url)
* [Request an integration](/help/request-an-integration)
