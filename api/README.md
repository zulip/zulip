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

If you are using Zulip Enterprise, you should also add

    site=<your Zulip Enterprise server's URI>

Alternatively, you may explicitly use "--user" and "--api-key" in our
examples, which is especially useful if you are running several bots
which share a home directory.  There is also a "--site" option for
setting the Zulip Enterprise server on the command line.

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
