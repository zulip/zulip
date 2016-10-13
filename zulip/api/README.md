#### Dependencies

The [Zulip API](https://zulip.com/api) Python bindings require the
following Python libraries:

* simplejson
* requests (version >= 0.12.1)


#### Installing

This package uses distutils, so you can just run:

    python setup.py install

#### Using the API

For now, the only fully supported API operation is sending a message.
The other API queries work, but are under active development, so
please make sure we know you're using them so that we can notify you
as we make any changes to them.

The easiest way to use these API bindings is to base your tools off
of the example tools under examples/ in this distribution.

If you place your API key in the config file `~/.zuliprc` the Python
API bindings will automatically read it in. The format of the config
file is as follows:

    [api]
    key=<api key from the web interface>
    email=<your email address>
    site=<your Zulip server's URI>
    insecure=<true or false, true means do not verify the server certificate>
    cert_bundle=<path to a file containing CA or server certificates to trust>

If omitted, these settings have the following defaults:

    site=https://api.zulip.com
    insecure=false
    cert_bundle=<the default CA bundle trusted by Python>

Alternatively, you may explicitly use "--user" and "--api-key" in our
examples, which is especially useful if you are running several bots
which share a home directory.

The command line equivalents for other configuration options are:

    --site=<your Zulip server's URI>
    --insecure
    --cert-bundle=<file>

You can obtain your Zulip API key, create bots, and manage bots all
from your Zulip [settings page](https://zulip.com/#settings).

A typical simple bot sending API messages will look as follows:

At the top of the file:

    # Make sure the Zulip API distribution's root directory is in sys.path, then:
    import zulip
    zulip_client = zulip.Client(email="your-bot@example.com", client="MyTestClient/0.1")

When you want to send a message:

    message = {
      "type": "stream",
      "to": ["support"],
      "subject": "your subject",
      "content": "your content",
    }
    zulip_client.send_message(message)

Additional examples:

    client.send_message({'type': 'stream', 'content': 'Zulip rules!',
                         'subject': 'feedback', 'to': ['support']})
    client.send_message({'type': 'private', 'content': 'Zulip rules!',
                         'to': ['user1@example.com', 'user2@example.com']})

send_message() returns a dict guaranteed to contain the following
keys: msg, result.  For successful calls, result will be "success" and
msg will be the empty string.  On error, result will be "error" and
msg will describe what went wrong.

#### Logging
The Zulip API comes with a ZulipStream class which can be used with the
logging module:

```
import zulip
import logging
stream = zulip.ZulipStream(type="stream", to=["support"], subject="your subject")
logger = logging.getLogger("your_logger")
logger.addHandler(logging.StreamHandler(stream))
logger.setLevel(logging.DEBUG)
logger.info("This is an INFO test.")
logger.debug("This is a DEBUG test.")
logger.warn("This is a WARN test.")
logger.error("This is a ERROR test.")
```

#### Sending messages

You can use the included `zulip-send` script to send messages via the
API directly from existing scripts.

    zulip-send hamlet@example.com cordelia@example.com -m \
        "Conscience doth make cowards of us all."

Alternatively, if you don't want to use your ~/.zuliprc file:

    zulip-send --user shakespeare-bot@example.com \
        --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5 \
        hamlet@example.com cordelia@example.com -m \
        "Conscience doth make cowards of us all."

#### Working with an untrusted server certificate

If your server has either a self-signed certificate, or a certificate signed
by a CA that you don't wish to globally trust then by default the API will
fail with an SSL verification error.

You can add `insecure=true` to your .zuliprc file.

    [api]
    site=https://zulip.example.com
    insecure=true

This disables verification of the server certificate, so connections are
encrypted but unauthenticated. This is not secure, but may be good enough
for a development environment.


You can explicitly trust the server certificate using `cert_bundle=<filename>`
in your .zuliprc file.

    [api]
    site=https://zulip.example.com
    cert_bundle=/home/bots/certs/zulip.example.com.crt

You can also explicitly trust a different set of Certificate Authorities from
the default bundle that is trusted by Python. For example to trust a company
internal CA.

    [api]
    site=https://zulip.example.com
    cert_bundle=/home/bots/certs/example.com.ca-bundle

Save the server certificate (or the CA certificate) in its own file,
converting to PEM format first if necessary.
Verify that the certificate you have saved is the same as the one on the
server.

The `cert_bundle` option trusts the server / CA certificate only for
interaction with the zulip site, and is relatively secure.

Note that a certificate bundle is merely one or more certificates combined
into a single file.
