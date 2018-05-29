A bridge for exchanging messages between [matrix.org](https://matrix.org) and Zulip!

### Install the bridge software

You can install the bridge software as follows:

1.  First, clone the Zulip API and install its dependencies:

    ```
    git clone https://github.com/zulip/python-zulip-api.git
    cd python-zulip-api
    python3 ./tools/provision
    ```

1. Next, enter the virtualenv, by running the `source` command printed
   at the end of the `provision` output.

1.  Then, run this to install the Matrix bridge software in your virtualenv.

    ```
    pip install -r zulip/integrations/matrix/requirements.txt
    ```

This will create a new Python virtual environment, with all the
dependences for this bridge installed.  You'll want to run the bridge
service inside this virtualenv.  If you later need to enter the
virtualenv (from e.g. a new shell), you can use the `source` command.

### Configure the bridge

{!create-stream.md!}

Next, on your Zulip settings page, create a generic bot for Matrix,
preferably with a formal name like `matrix-bot`.
It is important that you subscribe this bot to the stream which is going
to act as the bridge.
Note its username, API key and full name; you will use them in the
next step.

In `matrix_bridge_config.py` enter the following details under `zulip`
keyword:
```
"email": "matrix-bot@chat.zulip.org",
"api_key": "your_key",
"site": "https://chat.zulip.org",
"stream": "Stream which acts as the bridge",
"topic": "Topic of the stream"
```

Now, create a user on [matrix.org](https://matrix.org/), preferably with a
formal name like `zulip-bot`.

In `matrix_bridge_config.py` enter the follow details under `matrix` keyword:
```
"host": "https://matrix.org",
"username": "username of matrix.org user",
"password": "password of matrix.org user",
"room_id": "#room:matrix.org"
```

If you want to change the displayed message template in Matrix or Zulip,
change the variables `MATRIX_MESSAGE_TEMPLATE` and `ZULIP_MESSAGE_TEMPLATE`,
with a suitable template.

After the steps above have been completed, run `python matrix_bridge.py` to
start the mirroring.

**Congratulations! You have created the bridge successfully!**
