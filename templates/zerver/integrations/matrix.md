A bridge for exchanging messages between Matrix and Zulip!

### Setup the bridge:

1. `git clone https://github.com/zulip/python-zulip-api.git` - clone the [python-zulip-api](
  https://github.com/zulip/python-zulip-api) repository.

2. `cd python-zulip-api` - navigate into your cloned repository and use
  `python3 ./tools/provision` to install all requirements in a Python virtualenv.

3. The output of `provision` will end with a command of the form `source .../activate`;
  run that command to enter the new virtualenv.

4. Navigate to the
  [matrix integration](https://github.com/zulip/python-zulip-api/tree/master/zulip/integrations/matrix)
   and use `pip install -r requirements.txt` to install the dependencies.

Now you can start the next configuration step.

### Configure the bridge:

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
