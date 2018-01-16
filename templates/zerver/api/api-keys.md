# API keys

You can create bots on your [settings page](/#settings).
Once you have a bot, you can use its email and API key to send messages.</p>

Create a bot:
<img class="screenshot" src="/static/images/api/create-bot.png" />

Look for the bot's email and API key:
<img class="screenshot" src="/static/images/api/bot-key.png" />

If you prefer to send messages as your own user, you can also find your API key on your [settings page](/#settings).
When using our python bindings, you may either specify the user
and API key for each Client object that you initialize, or let the binding look for
them in your `~/.zuliprc`, the default config file, which you can create as follows:

```
[api]
key=BOT_API_KEY
email=BOT_EMAIL_ADDRESS
```

Additionally, you can also specify the parameters as environment variables as follows:

```
export ZULIP_CONFIG=/path/to/zulipconfig
export ZULIP_EMAIL=BOT_EMAIL_ADDRESS
export ZULIP_API_KEY=BOT_API_KEY
```

The parameters specified in environment variables would override the parameters
provided in the config file. For example, if you specify the variable `key`
in the config file and specify `ZULIP_API_KEY` as an environment variable,
the value of `ZULIP_API_KEY` would be considered.

The following variables can be specified:

1. `ZULIP_CONFIG`
2. `ZULIP_API_KEY`
3. `ZULIP_EMAIL`
4. `ZULIP_SITE`
5. `ZULIP_CERT`
6. `ZULIP_CERT_KEY`
7. `ZULIP_CERT_BUNDLE`
