# API keys and `zuliprc` files

An **API key** is how a user or bot can identify their account to Zulip.

A **`zuliprc` file** is a configuration file written in the [INI file
format](https://en.wikipedia.org/wiki/INI_file), which contains key-value
pairs, such as an API key and other configuration values, that are
necessary for using the Zulip API with a specific user or bot account on
a Zulip server, for example:

```
[api]
key=<bot API key>
email=<bot email address>
site=<Zulip server's URL>
...
```

For the official
clients, such as the [Python bindings](/api/configuring-python-bindings),
we recommend [downloading a `zuliprc` file](#download-a-zuliprc-file).

## Get an API key

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

To invalidate an existing API key, you have to generate a new key. Generating a
new API key will immediately log you out of this account on all mobile devices.

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

### Download a `zuliprc` file

{start_tabs}

{tab|for-a-bot}

{settings_tab|your-bots}

1. In the **Actions** column, click the **manage bot**
   (<i class="zulip-icon zulip-icon-user-cog"></i>) icon,
   and scroll down to **Zuliprc configuration**.

1. Click the **download**
   (<i class="zulip-icon zulip-icon-download"></i>) icon
   to download the bot's `zuliprc` file, or the **copy**
   (<i class="zulip-icon zulip-icon-copy"></i>) icon to
   copy the file's content to your clipboard.

!!! warn ""

    Anyone with a bot's API key can impersonate the bot, so be careful with it!

{tab|for-yourself}

{settings_tab|account-and-privacy}

1. Under **API key**, click **Manage your API key**.

1. Enter your password, and click **Get API key**. If you don't know your
   password, click **reset it** and follow the
   instructions from there.

1. Click **Download zuliprc** to download your `zuliprc` file.

1. (optional) If you'd like your credentials to be used by default
   when using the Zulip API on your computer, move the `zuliprc` file
   to `~/.zuliprc` in your home directory.

!!! warn ""

    Anyone with your API key can impersonate you, so be doubly careful with it.

{end_tabs}

### Configuration keys and environment variables

The keys you can use in a `zuliprc` file (and their equivalent
[environment variables](https://en.wikipedia.org/wiki/Environment_variable))
can be found in the following table:

| `zuliprc` key | Environment variable | Required | Description |
| --- | --- | --- | --- |
| `key` | `ZULIP_API_KEY` | Yes | The user's [API key](#get-an-api-key). |
| `email` | `ZULIP_EMAIL` | Yes | The email address of the user who owns the API key mentioned above. |
| `site` | `ZULIP_SITE` | No | URL where the Zulip server is located. |
| `client_cert_key` | `ZULIP_CERT_KEY` | No | Path to the SSL/TLS private key that the binding should use to connect to the server. |
| `client_cert`| `ZULIP_CERT` | No* | The public counterpart of `client_cert_key`/`ZULIP_CERT_KEY`. _*This setting is required if a cert key has been set._ |
| `client_bundle` | `ZULIP_CERT_BUNDLE` | No | Path where the server's PEM-encoded certificate is located. CA certificates are also accepted, in case those CA's have issued the server's certificate. Defaults to the built-in CA bundle trusted by Python. |
| `insecure` | `ZULIP_ALLOW_INSECURE` | No | Allows connecting to Zulip servers with an invalid SSL/TLS certificate. Please note that enabling this will make the HTTPS connection insecure. Defaults to `false`. |

## Related articles

* [Configuring the Python bindings](/api/configuring-python-bindings)
