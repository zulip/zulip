A bridge for exchanging messages between [matrix.org](https://matrix.org) and Zulip!

{!install-matrix.md!}

### Configure the bridge

{!create-stream.md!}

1. Next, on your Zulip settings page, create a generic bot for Matrix,
   preferably with a formal name like `matrix-bot`.

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
