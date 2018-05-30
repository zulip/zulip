A bridge for exchanging messages between IRC and Zulip, powered by
[the Zulip Matrix integration](/integrations/doc/matrix).

{!install-matrix.md!}

### Configure the bridge

{!create-stream.md!}

1. Next, on your Zulip settings page, create a generic bot for Matrix,
preferably with a formal name like `irc-bot`.

1. Subscribe this bot to the Zulip stream where you'd like the bridge
   traffic to be sent.

1.  Edit `zulip/integrations/matrix/matrix_bridge_config.py`, providing
    the following values for the `zulip` section (the first 3 values
    come from a `zuliprc` file):

    ```
    "zulip": {
        "email": "matrix-bot@chat.zulip.org",
        "api_key": "your_key",
        "site": "https://chat.zulip.org",
        "stream": "Stream which acts as the bridge",
        "topic": "Topic of the stream"
    }
    ```

1. Now, create a user on [matrix.org](https://matrix.org/), preferably
   with a formal name like `zulip-bot`.
   Matrix has been bridged to several popular
   [IRC Networks](https://github.com/matrix-org/matrix-appservice-irc/wiki/Bridged-IRC-networks),
   where the `Room alias format` refers to the `room_id` for the
   corresponding IRC channel.  For example, the `room_id` would be
   `#freenode_#zulip-test:matrix.org` for the freenode channel
   `#zulip-test`.

1.  Edit `matrix_bridge_config.py` to add the Matrix-side settings:

    ```
    "matrix": {
        "host": "https://matrix.org",
        "username": "username of matrix.org user",
        "password": "password of matrix.org user",
        "room_id": "#room:matrix.org"
    }
    ```

1. After the steps above have been completed, run `python matrix_bridge.py` to
start mirroring content.

If you want to customize the message formatting, you can do so by
editing the variables `MATRIX_MESSAGE_TEMPLATE` and
`ZULIP_MESSAGE_TEMPLATE` in
`zulip/integrations/matrix/matrix_bridge.py`, with a suitable
template.

**Congratulations! You have created the bridge successfully!**

Here is an example Zulip-IRC bridge created through Matrix:

Your Zulip notifications may look like:

![](/static/images/integrations/irc/001.png)

Your IRC notifications may look like:

![](/static/images/integrations/irc/002.png)

### Caveats

There are certain
[IRC channels](https://github.com/matrix-org/matrix-appservice-irc/wiki/Channels-from-which-the-IRC-bridge-is-banned)
where the Matrix.org IRC bridge has been banned for technical reasons.
You can't mirror those IRC channels using this integration.
