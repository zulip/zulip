# Configuring the Python bindings

Zulip provides a set of tools that allows interacting with its API more
easily, called the [Python bindings](https://pypi.python.org/pypi/zulip/).
One of the most notable use cases for these bindings are bots developed
using Zulip's [bot framework](/api/writing-bots).

In order to use them, you need to configure them with your identity
(account, API key, and Zulip server URL). There are a few ways to
achieve that:

- Using a `zuliprc` file, referenced via the `--config-file` option or
  the `config_file` option to the `zulip.Client` constructor
  (recommended for bots).
- Using a `zuliprc` file in your home directory at `~/.zuliprc`
  (recommended for your own API key).
- Using the [environment
  variables](https://en.wikipedia.org/wiki/Environment_variable)
  documented below.
- Using the `--api-key`, `--email`, and `--site` variables as command
  line parameters.
- Using the `api_key`, `email`, and `site` parameters to the
  `zulip.Client` constructor.

## Download a `zuliprc` file

{start_tabs}

{tab|for-a-bot}

{settings_tab|your-bots}

1. Click the **download** (<i class="fa fa-download"></i>) icon on the profile
   card of the desired bot to download the bot's `zuliprc` file.

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

## Configuration keys and environment variables

`zuliprc` is a configuration file written in the
[INI file format](https://en.wikipedia.org/wiki/INI_file),
which contains key-value pairs as shown in the following example:

```
[api]
key=<API key from the web interface>
email=<your email address>
site=<your Zulip server's URI>
...
```

The keys you can use in this file (and their equivalent environment variables)
can be found in the following table:

<table class="table">
    <thead>
        <tr>
            <th><code>zuliprc</code> key</th>
            <th>Environment variable</th>
            <th>Required</th>
            <th>Description</th>
        </tr>
    </thead>
    <tr>
        <td><code>key</code></td>
        <td><code>ZULIP_API_KEY</code></td>
        <td>Yes</td>
        <td>
            <a href="/api/api-keys">API key</a>, which you can get through
            Zulip's web interface.
        </td>
    </tr>
    <tr>
        <td><code>email</code></td>
        <td><code>ZULIP_EMAIL</code></td>
        <td>Yes</td>
        <td>
            The email address of the user who owns the API key mentioned
            above.
        </td>
    </tr>
    <tr>
        <td><code>site</code></td>
        <td><code>ZULIP_SITE</code></td>
        <td>No</td>
        <td>
            URL where your Zulip server is located.
        </td>
    </tr>
    <tr>
        <td><code>client_cert_key</code></td>
        <td><code>ZULIP_CERT_KEY</code></td>
        <td>No</td>
        <td>
            Path to the SSL/TLS private key that the binding should use to
            connect to the server.
        </td>
    </tr>
    <tr>
        <td><code>client_cert</code></td>
        <td><code>ZULIP_CERT</code></td>
        <td>No*</td>
        <td>
            The public counterpart of <code>client_cert_key</code>/
            <code>ZULIP_CERT_KEY</code>. <i>This setting is required if a cert
            key has been set.</i>
        </td>
    </tr>
    <tr>
        <td><code>client_bundle</code></td>
        <td><code>ZULIP_CERT_BUNDLE</code></td>
        <td>No</td>
        <td>
            Path where the server's PEM-encoded certificate is located. CA
            certificates are also accepted, in case those CA's have issued the
            server's certificate. Defaults to the built-in CA bundle trusted
            by Python.
        </td>
    </tr>
    <tr>
        <td><code>insecure</code></td>
        <td><code>ZULIP_ALLOW_INSECURE</code></td>
        <td>No</td>
        <td>
            Allows connecting to Zulip servers with an invalid SSL/TLS
            certificate. Please note that enabling this will make the HTTPS
            connection insecure. Defaults to <code>false</code>.
        </td>
    </tr>
</table>

## Related articles

* [Installation instructions](/api/installation-instructions)
* [API keys](/api/api-keys)
* [Running bots](/api/running-bots)
* [Deploying bots](/api/deploying-bots)
