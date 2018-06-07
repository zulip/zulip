A bridge for exchanging messages between IRC and Zulip, powered by
[the Zulip Matrix integration](/integrations/doc/matrix).

{!install-matrix.md!}

### Configure the bridge

{!create-stream.md!}

1.  Next, on your Zulip settings page, create a generic bot for Matrix,
    preferably with a formal name like `irc-bot`.

1.  Subscribe this bot to the Zulip stream where you'd like the bridge
    traffic to be sent.

1.  For the next stage, generate a new sample configuration file by either:

    -   Downloading the information from the bot settings page into a `zuliprc`
        file, then running:

        ```
        python matrix_bridge.py --write-sample-config <config_path> --from-zuliprc <zuliprc>`
        ```

        where `<zuliprc>` is the path to the `zuliprc` file downloaded, and
        `<config_path>` is the target path to place the new configuration file.

        The new configuration file will automatically contain values from the `zuliprc` file.

    -   Alternatively, first running the following:

        ```
        python matrix_bridge.py --write-sample-config <config_path>
        ```

        where `<config_path>` is the target path to place the new configuration file.

        Then accessing the bot settings page and noting the information for your bot
        (`USERNAME`, `API KEY` and the server name, eg. `https://chat.zulip.org`),
        and amending the first three lines in the `[zulip]` section to contain the
        information noted from the bot settings page.

1.  After the previous step, the zulip part of the configuration file should
    then look something like the following, where the content of the first three
    lines should match the bot details on the settings page:

    ```
    [zulip]
    email = matrix-bot@chat.zulip.org
    api_key = aPiKeY
    site = https://chat.zulip.org
    stream = stream which acts as the bridge
    topic = topic in the stream
    ```

1.  Now, create a user on [matrix.org](https://matrix.org/), preferably
    with a formal name like `zulip-bot`.

1.  Using the username and password of the user created in the previous step,
    amend the configuration file to add the Matrix-side settings:

    ```
    [matrix]
    host = https://matrix.org
    username = matrix_username
    password = matrix_password
    room_id = #room:matrix.org
    ```

    NOTE: The `room_id` specifies where the Matrix end of the bridge connects
    to, which for IRC generally takes the form of `#<network>_#<channel>:matrix.org` if
    bridging through the `matrix.org` server. For example, the `room_id` would
    be `#freenode_#zulip-test:matrix.org` for the freenode channel
    `#zulip-test`. Matrix has been bridged to several popular
    [IRC Networks](https://github.com/matrix-org/matrix-appservice-irc/wiki/Bridged-IRC-networks),
    where the `Room alias format` refers to the `room_id` for the
    corresponding IRC channel.

1.  After the steps above have been completed, run the following command to
    start the matrix bridge:

    ```
    python matrix_bridge.py -c <config_path>
    ```

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
