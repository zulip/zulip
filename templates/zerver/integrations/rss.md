Get service alerts, news, and new blog posts right in Zulip with our
RSS integration!

!!! tip ""

    Note that [the Zapier integration][1] is usually a simpler way to
    integrate RSS with Zulip.

[1]: ./zapier

1.  {!create-channel.md!}

1.  {!create-an-incoming-webhook.md!}

1.  {!download-python-bindings.md!}

1.  The RSS integration will be installed to a location like
    `/usr/local/share/zulip/integrations/rss/rss-bot`.

1.  Follow the instructions in the `rss-bot` script for configuring the
    bot, adding your subscriptions, and setting up a cron job to run
    the bot.

{!congrats.md!}

![RSS bot message](/static/images/integrations/rss/001.png)
