#### Dependencies

The Humbug API Python bindings require the following Python libraries:

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

If you place your API key in the config file `~/.humbugrc` the Python
API bindings will automatically read it in. The format of the config
file is as follows:

    [api]
    key=<api key from the web interface>
    email=<your email address>

Alternatively, you may explicitly use "--user" and "--api-key" in our
examples, which is especially useful if you are running several bots
which share a home directory.

You can obtain your Humbug API key, create bots, and manage bots all
from your Humbug [settings page](https://humbughq.com/#settings).

A typical simple bot sending API messages will look as follows:

At the top of the file:

    # Make sure the Humbug API distribution's root directory is in sys.path, then:
    import humbug
    humbug_client = humbug.Client(email="your-bot@example.com")

When you want to send a message:

    message = {
      "type": "stream",
      "to": ["support"],
      "subject": "your subject",
      "content": "your content",
    }
    humbug_client.send_message(message)

Additional examples:

    client.send_message({'type': 'stream', 'content': 'Humbug rules!',
                         'subject': 'feedback', 'to': ['support']})
    client.send_message({'type': 'private', 'content': 'Humbug rules!',
                         'to': ['user1@example.com', 'user2@example.com']})

send_message() returns a dict guaranteed to contain the following
keys: msg, result.  For successful calls, result will be "success" and
msg will be the empty string.  On error, result will be "error" and
msg will describe what went wrong.

#### Sending messages

You can use the included `humbug-send` script to send messages via the
API directly from existing scripts.

    humbug-send hamlet@example.com cordelia@example.com -m \
        "Conscience doth make cowards of us all."

Alternatively, if you don't want to use your ~/.humbugrc file:

    humbug-send --user shakespeare-bot@example.com \
        --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5 \
        hamlet@example.com cordelia@example.com -m \
        "Conscience doth make cowards of us all."
