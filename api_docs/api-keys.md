# API keys

An **API key** is how a bot identifies itself to Zulip. For the official
clients, such as the Python bindings, we recommend [downloading a `zuliprc`
file](/api/configuring-python-bindings#download-a-zuliprc-file). This file
contains an API key and other necessary configuration values for using the
Zulip API with a specific account on a Zulip server.

## Get API key

{start_tabs}

{tab|for-a-bot}

{settings_tab|your-bots}

1. In the **Actions** column, click the **manage bot**
   (<i class="zulip-icon zulip-icon-user-cog"></i>) icon,
   and scroll down to **API key**.

1. Click the **copy**
   (<i class="zulip-icon zulip-icon-copy"></i>) icon to
   copy the bot's API key to your clipboard.

!!! warn ""

    Anyone with a bot's API key can impersonate the bot, so be careful with it!

{tab|for-yourself}

{settings_tab|account-and-privacy}

1. Under **API key**, click **Manage your API key**.

1. Enter your password, and click **Get API key**. If you don't know your
   password, click **reset it** and follow the instructions from there.

1. Copy your API key.

!!! warn ""

    Anyone with your API key can impersonate you, so be doubly careful with it.

{end_tabs}

## Invalidate an API key

To invalidate an existing API key, you have to generate a new key.

{start_tabs}

{tab|for-a-bot}

{settings_tab|your-bots}

1. In the **Actions** column, click the **manage bot**
   (<i class="zulip-icon zulip-icon-user-cog"></i>) icon,
   and scroll down to **API key**.

1. Click the **generate new API key**
   (<i class="zulip-icon zulip-icon-refresh-cw"></i>) icon.

{tab|for-yourself}

{settings_tab|account-and-privacy}

1. Under **API key**, click **Manage your API key**.

1. Enter your password, and click **Get API key**. If you don't know your
   password, click **reset it** and follow the instructions from there.

1. Click **Generate new API key**

{end_tabs}

## Related articles

* [Configuring the Python bindings](/api/configuring-python-bindings)
