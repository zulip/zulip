A bridge for exchanging messages between [matrix.org](https://matrix.org) and Zulip!

{!install-matrix.md!}

### Configure the bridge

1. {!create-stream.md!}

1. On your {{ settings_html|safe }}, create a **Generic** bot for
   {{ integration_display_name }}. Subscribe this bot to the stream
   created in step 1.

1. Open `zulip/integrations/matrix/matrix_bridge_config.py` with your
   favorite editor, and change the following lines in the `zulip`
   section:

    ```
    "zulip": {
        "email": "matrix-bot@chat.zulip.org",
        "api_key": "your_key",
        "site": "https://chat.zulip.org",
        "stream": "Stream which acts as the bridge",
        "topic": "Topic of the stream"
    }
    ```

    **email**, **api_key**, and **site** should come from your
    {{ integration_display_name }} bot's `zuliprc` file. Set **stream**
    to the name of the stream created in step 1, and set **topic** to
    a topic of your choice.

1. Create a user on [matrix.org](https://matrix.org/), preferably
   with a descriptive name such as `zulip-bot`.

1. Open `matrix_bridge_config.py`, and provide your Matrix credentials
   in the `matrix` section:

    ```
    "matrix": {
        "host": "https://matrix.org",
        "username": "username of matrix.org user",
        "password": "password of matrix.org user",
        "room_id": "#room:matrix.org"
    }
    ```

1. Run `python matrix_bridge.py` to start mirroring content.

!!! tip ""

    If you want to customize the message formatting, you can do so by
    editing the variables `MATRIX_MESSAGE_TEMPLATE` and
    `ZULIP_MESSAGE_TEMPLATE` in
    `zulip/integrations/matrix/matrix_bridge.py`.

**Congratulations! You have created the bridge successfully!**
