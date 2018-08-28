### Configure the bridge

1. {!create-stream.md!}

1. [Create a bot](/help/add-a-bot-or-integration), using **Generic bot** for
   the bot type. Subscribe this bot to the stream you just created.

1. Open `zulip/integrations/matrix/matrix_bridge_config.py` in your cloned
   repository, and update the following section:

    ```
    ('zulip', OrderedDict((
        ('email', 'glitch-bot@chat.zulip.org'),
        ('api_key', 'aPiKeY'),
        ('site', 'https://chat.zulip.org'),
        ('stream', 'test here'),
        ('topic', 'matrix'),
    ))),
    ```

    Replace the **email**, **api_key**, and **site** values with those from
    your bot's `zuliprc` file, and set **stream** to the name of the stream
    created in step 1. Set **topic** to a topic of your choice, like
    `IRC mirror`.

1. Create a user on [matrix.org](https://matrix.org/), preferably
   with a descriptive name such as `zulip-bot`.

1. Open `zulip/integrations/matrix/matrix_bridge_config.py` again, and update
   the following section with your Matrix credentials:

    ```
    ('matrix', OrderedDict((
        ('host', 'https://matrix.org'),
        ('username', 'username'),
        ('password', 'password'),
        ('room_id', '#zulip:matrix.org'),
    ))),
    ```

    {% if 'IRC' in integration_display_name %}

    Matrix has been bridged to several popular
    [IRC Networks](https://github.com/matrix-org/matrix-appservice-irc/wiki/Bridged-IRC-networks).
    **Room alias format** refers to the `room_id` for the corresponding IRC channel.
    For instance, for the freenode channel `#zulip-test`, the `room_id` would be
    `#freenode_#zulip-test:matrix.org`.

    {% endif %}

1. Run `python matrix_bridge.py` from inside the Python virtual environment
   to start mirroring content.

!!! tip ""

    If you want to customize the message formatting, you can do so by
    editing the variables `MATRIX_MESSAGE_TEMPLATE` and `ZULIP_MESSAGE_TEMPLATE`
    in `zulip/integrations/matrix/matrix_bridge.py`.
