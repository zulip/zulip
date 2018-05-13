# API keys

You can create bots on your [settings page](/#settings).
Once you have a bot, you can use its email and API key to send messages.

Create a bot:

<img class="screenshot" src="/static/images/api/create-bot.png" />

Look for the bot's email and API key:

<img class="screenshot" src="/static/images/api/bot-key.png" />

If you prefer to send messages as your own user, you can also find your API key on your [settings page](/#settings):

<img class="screenshot" src="/static/images/api/user-api-key.png" />

When using our Python bindings, you may either specify the user
and API key for each Client object that you initialize, or let the binding look for
them in your `~/.zuliprc`. An automatically generated default version can be found in
your bot's details:

<img class="screenshot" src="/static/images/api/download-zuliprc.png" />

Another alternative is manually creating your own `.zuliprc` file, or setting
environment variables that are equivalent. You can find out more about these
methods [here](/api/configuring-python-bindings).

