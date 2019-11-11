# API keys and zuliprc files

A `.zuliprc` file is a plain text document that goes in your home directory
and looks like this:

```
[api]
key=<api key from the web interface>
email=<your email address>
site=<your Zulip server's URI>
...
```

Only the first two fields, i.e. `key` and `email`, are required. All possible
fields are documented in the [table below](#configure-environment-variables).
The values of these fields are needed to configure the set of tools that allow
interacting with the Zulip API more easily.

For example, the [Python bindings](/api/installation-instructions) are often
configured with a `.zuliprc` file. The API key and other settings can be utilized
to develop bots using Zulip's [bot framework](/api/writing-bots). An **API key**
is how a bot identifies itself to Zulip.

## Download zuliprc

{start_tabs}

{tab|your-bots}

!!! warn ""
    **Warning:**
    Anyone with a bot's API key can impersonate the bot, so be careful with it!

{settings_tab|your-bots}
2. Click [Add a new bot](/help/add-a-bot-or-integration).
3. Click the **download** (<i class="fa fa-download"></i>) icon
    under the bot's name.

!!! tip ""
    To invalidate an API key, go to the **Active Bots** panel, and click
    the **refresh** (<i class="fa fa-refresh"></i>) icon.

{tab|your-account}

!!! warn ""
    **Warning:**
    Anyone with your API key can impersonate you, so be doubly careful with it.

{settings_tab|your-account}
2. Under **API key**, click **Show/change your API key**.
3. Enter your password and click **Get API key**.
4. Click the **Download .zuliprc** button.

!!! tip ""
    To invalidate an API key, follow the instructions above, and click
    **Generate new API key**.

{end_tabs}

## Configure environment variables

Alternatively, you can set up
[environment variables](https://en.wikipedia.org/wiki/Environment_variable) that
correspond to the fields in the `.zuliprc` file as shown in the following table.

Notice that configuration of bots using environment variables is not supported,
but you can configure multiple bots by downloading your `.botserverrc` file
which includes all active outgoing webhook bots in Zulip Botserver format.

<table class="table">
    <thead>
        <tr>
            <th>.zuliprc field</th>
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
            API key which you can get through
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
            <code>ZULIP_CERT_KEY</code>. *<i>This setting is required if a cert
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
    <tr>
        <td><code>token</code></td>
        <td><i>N/A (Not Supported)</i></td>
        <td>No</td>
        <td>
            The outgoing webhook endpoint server authenticates
            requests coming from your bot using this value.
        </td>
    </tr>
</table>
