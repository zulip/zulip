# The Zulip API

Zulip's APIs allow you to integrate other services with Zulip.  This
guide should help you find the API you need:

* First, check if the tool you'd like to integrate with Zulip
[already has a native integration](/integrations).
* Next, check if [Zapier](https://zapier.com/apps) or
  [IFTTT](https://ifttt.com/search/services) has an integration;
  Zulip's native integrations with Zapier and IFTTT often allow
  integrating a new service with Zulip without writing any code.
* If you'd like to send content into Zulip, you can
  [write a native incoming webhook integration](/api/integration-guide#webhook-integrations)
  or use [Zulip's API for sending messages](/api/stream-message).
* If you're building an interactive bot that reacts to activity inside
  Zulip, you'll want to look at Zulip's
  [Python framework for interactive bots](/api/running-bots) or
  [Zulip's real-time events API](/api/get-events-from-queue).
* If you'd like to do something else, check out the full
  [REST API](/api/rest), generally starting with
  [installing the API client bindings](/api/installation-instructions).

