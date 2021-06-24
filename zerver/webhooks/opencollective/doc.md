This integration currently supports getting notifications to a stream of your Zulip instance,
when a new member signs-up on an **Open Collective** page.

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Go to [Open Collective Website](https://opencollective.com/), find
your desired collective page, then go to *Settings* -> *Webhooks*, paste the
bot URL and choose *Activity* -> *New Member*.

{!congrats.md!}

![](/static/images/integrations/opencollective/001.png)

In the future, this integration can be developed in order to
support other types of *Activity* such as *New Transaction*, *Subscription Canceled* etc.
