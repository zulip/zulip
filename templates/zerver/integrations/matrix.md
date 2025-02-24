Exchange messages between [matrix.org](https://matrix.org) and Zulip! If
you're looking to mirror an IRC channel in particular, we recommend our
[direct IRC integration](/integrations/doc/irc).

### Install the bridge software

1. Clone the Zulip API repository, and install its dependencies.

    ```
    git clone https://github.com/zulip/python-zulip-api.git
    cd python-zulip-api
    python3 ./tools/provision
    ```

    This will create a new Python virtualenv. You'll run the bridge service
    inside this virtualenv.

1. Activate the virtualenv by running the `source` command printed
   at the end of the output of the previous step.

1. Install the Matrix bridge software in your virtualenv, by running:

    ```
    pip install -r zulip/integrations/bridge_with_matrix/requirements.txt
    ```

### Configure the bridge

1. {!create-a-generic-bot.md!}
   Download the bot's `zuliprc` configuration file to your computer.

1. [Subscribe the bot](/help/subscribe-users-to-a-channel) to the Zulip
   stream that will contain the mirror.

1. Inside the virtualenv you created above, run

    ```
    python zulip/integrations/bridge_with_matrix/matrix_bridge.py \
    --write-sample-config matrix_bridge.conf --from-zuliprc <path/to/zuliprc>
    ```

    where `<path/to/zuliprc>` is the path to the `zuliprc` file you downloaded.

1. Create a user on [matrix.org](https://matrix.org/) or another matrix
   server, preferably with a descriptive name like `zulip-bot`.

1. Edit `matrix_bridge.conf` to look like this:

    ```
    [zulip]
    email = bridge-bot@chat.zulip.org
    api_key = aPiKeY
    site = https://chat.zulip.org
    stream = "stream name"
    topic = "{{ integration_display_name }} mirror"
    [matrix]
    host = https://matrix.org
    username = <your matrix username>
    password = <your matrix password>
    room_id = #room:matrix.org
    ```

    The first three values should already be there; the rest you'll have to fill in.
    Make sure **stream** is set to the stream the bot is
    subscribed to.

    {% if 'IRC' in integration_display_name %}

    NOTE: For matrix.org, the `room_id` generally takes the form
    `#<irc_network>_#<channel>:matrix.org`. You can see the format for
    several popular IRC networks
    [here](https://github.com/matrix-org/matrix-appservice-irc/wiki/Bridged-IRC-networks), under
    the "Room alias format" column.

    For example, the `room_id` for the `#zulip-test` channel on freenode is
    `#freenode_#zulip-test:matrix.org`.

    {% endif %}

1. Run the following command to start the matrix bridge:

    ```
    python zulip/integrations/bridge_with_matrix/matrix_bridge.py -c matrix_bridge.conf
    ```

!!! tip ""

    You can customize the message formatting by
    editing the variables `MATRIX_MESSAGE_TEMPLATE` and `ZULIP_MESSAGE_TEMPLATE`
    in `zulip/integrations/bridge_with_matrix/matrix_bridge.py`.

**Note**: There are a handful of
[IRC channels](https://github.com/matrix-org/matrix-appservice-irc/wiki/Channels-from-which-the-IRC-bridge-is-banned)
that have temporarily banned the Matrix.org IRC bridge.
You can't currently mirror those channels using this integration.
