Mirror an IRC channel in Zulip!

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

1. Go to the directory containing the bridge script if you haven't already done so

    ```
    cd zulip/integrations/bridge_with_irc
    ```

1. Install the bridge dependencies in your virtualenv, by running:

     ```
     pip install -r requirements.txt
     ```

### Configure the bridge

1. {!create-a-generic-bot.md!}
   Download the bot's `zuliprc` configuration file to your computer.

1. [Subscribe the bot](/help/add-or-remove-users-from-a-channel) to the Zulip
   stream that will contain the mirror.

1. Inside the virtualenv you created above, run:

    ```
    python irc-mirror.py --irc-server=IRC_SERVER --channel=<CHANNEL> --nick-prefix=<NICK> \
    --stream=<STREAM> [--topic=<TOPIC>] \
    --site=<zulip.site> --user=<bot-email> \
    --api-key=<api-key>
    ```

    `--topic` is a Zulip topic, is optionally specified, defaults to "IRC".

Example command:

```
./irc-mirror.py --irc-server=irc.freenode.net --channel='#python-mypy' --nick-prefix=irc_mirror \
--stream='test here' --topic='#mypy' \
--site="https://chat.zulip.org" --user=bot@email.com \
--api-key=DeaDbEEf
```

**Congratulations! You're done!**

Your Zulip messages may look like:

![IRC message on Zulip](/static/images/integrations/irc/001.png)

Your IRC messages may look like:

![Zulip message on IRC](/static/images/integrations/irc/002.png)
