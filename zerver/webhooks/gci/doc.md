If you are a participating organization with
[Google Code-in](https://developers.google.com/open-source/gci/),
you can now get Task notifications in Zulip!

{!create-stream.md!}

{!create-bot-construct-url.md!}

To set up the webhook, send the URL you constructed above to
gci-support@google.com to be configured.

Note that because the GCI outgoing webhook API is very new, this
integration only supports the "abandon" event type.  We plan to expand
it further as the other event types are documented.

{!congrats.md!}

![](/static/images/integrations/gci/001.png)
