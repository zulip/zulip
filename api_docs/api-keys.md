# API keys

An **API key** is how a bot identifies itself to Zulip. For the official
clients, such as the Python bindings, we recommend [downloading a `zuliprc`
file](/api/configuring-python-bindings#download-a-zuliprc-file). This file
contains an API key and other necessary configuration values for using the
Zulip API with a specific account on a Zulip server.

## Get a bot's API key

{start_tabs}

{tab|desktop-web}

{settings_tab|your-bots}

1. Click **Active bots**.

1. Find your bot. The bot's API key is under **API KEY**.

{end_tabs}

!!! warn ""

    Anyone with a bot's API key can impersonate the bot, so be careful with it!

## Get your API key

{start_tabs}

{tab|desktop-web}

{settings_tab|account-and-privacy}

1. Under **API key**, click **Manage your API key**.

1. Enter your password, and click **Get API key**. If you don't know your
   password, click **reset it** and follow the instructions from there.

1. Copy your API key.

{end_tabs}

!!! warn ""

    Anyone with your API key can impersonate you, so be doubly careful with it.


## Invalidate an API key

To invalidate an existing API key, you have to generate a new key.

### Invalidate a bot's API key

{start_tabs}

{tab|desktop-web}

{settings_tab|your-bots}

1. Click **Active bots**.

1. Find your bot.

1. Under **API KEY**, click the **refresh** (<i class="fa fa-refresh"></i>) icon
   to the right of the bot's API key.

{end_tabs}

### Invalidate your API key

{start_tabs}

{tab|desktop-web}

{settings_tab|account-and-privacy}

1. Under **API key**, click **Manage your API key**.

1. Enter your password, and click **Get API key**. If you don't know your
   password, click **reset it** and follow the instructions from there.

1. Click **Generate new API key**

{end_tabs}

## Related articles

* [Configuring the Python bindings](/api/configuring-python-bindings)
