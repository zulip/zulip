Get service alerts, news, and new blog posts right in Zulip with our
RSS integration!

{!create-stream.md!}

Next, on your {{ settings_html|safe }}, create an RSS bot.

{!download-python-bindings.md!}

The RSS integration will be installed to a location like
`/usr/local/share/zulip/integrations/rss/rss-bot`.

Follow the instructions in the `rss-bot` script for configuring the
bot, adding your subscriptions, and setting up a cron job to run
the bot.

{!congrats.md!}

![](/static/images/integrations/rss/001.png)
