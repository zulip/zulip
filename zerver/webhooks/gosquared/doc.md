{!create-stream.md!}

The integration will automatically use the default stream `gosquared`
if no stream is supplied, though you will still need to create the
stream manually even though it's the default.

{!create-bot-construct-url.md!}

{!append-topic.md!}

Go to the account settings page of your GoSquared account and under
**Project Settings > Services > Webhook > Add New**, add the above
URL under the section **Enter a URL to receive requests:** and name
the integration, Zulip.

![](/static/images/integrations/gosquared/001.png)

Under notifications of your GoSquared account page, press
**Add New Notification** and select when and why you want to be
notified through Zulip. After you're done, remember to check the box
of the webhook corresponding to Zulip.

{!congrats.md!}

![](/static/images/integrations/gosquared/000.png)
