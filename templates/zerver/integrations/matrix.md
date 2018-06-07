A bridge for exchanging messages between [matrix.org](https://matrix.org) and Zulip!

{!install-matrix.md!}

### Configure the bridge

1.  {!create-stream.md!}

1.  On your {{ settings_html|safe }}, create a **Generic** bot for
    {{ integration_display_name }} with a formal name such as `matrix-bot`.

1.  Subscribe this bot to the Zulip stream created in step 1, where the bridge
    traffic will be sent.

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
        information noted from the bot settings page, using your favorite editor.

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

    **email**, **api_key**, and **site** should come from your
    {{ integration_display_name }} bot's `zuliprc` file. Set **stream**
    to the name of the stream created in step 1, and set **topic** to
    a topic of your choice.

1.  Create a user on [matrix.org](https://matrix.org/), preferably
    with a descriptive name like `zulip-bot`.

1.  Using the username and password of the user created in the previous step,
    amend the configuration file to add the Matrix-side settings, using your
    favorite editor:

    ```
    [matrix]
    host = https://matrix.org
    username = matrix_username
    password = matrix_password
    room_id = #room:matrix.org
    ```

    NOTE: The `room_id` specifies where the Matrix end of the bridge connects to.

1.  After the steps above have been completed, run the following command to
    start the matrix bridge:

    ```
    python matrix_bridge.py -c <config_path>
    ```

!!! tip ""

    If you want to customize the message formatting, you can do so by
    editing the variables `MATRIX_MESSAGE_TEMPLATE` and
    `ZULIP_MESSAGE_TEMPLATE` in
    `zulip/integrations/matrix/matrix_bridge.py`.

**Congratulations! You have created the bridge successfully!**
