You can set up a bridge to mirror messages between Slack channels and Zulip
topics. Any message sent to the Slack channel will appear in the connected Zulip
topic, and vice versa. This is a great option to enable inter-team communication
for organizations where some teams
primarily use Zulip while others primarily use Slack. 

Once the initial setup is complete, you can mirror additional channels/topics by simply
subscribing the Slack bot you've created to those channels. Teams can thus
mirror additional channels without assistance from IT/admins.

Note that there are two alternative ways to bridge between Slack and Zulip:

* [Matterbridge](https://github.com/42wim/matterbridge) is third-party
  integration option with similar functionality. It requires a configuration
  change for each additional channel/topic pair you wish to mirror, but may be
  convenient if you also need to bridge between other pairs of chat protocols.

* [Slack-to-Zulip](/integrations/doc/slack) is a one-way integration that sends
  Slack messages to a Zulip topic. It is very easy to set up.

See also our documentation for
[importing your organization from Slack](/help/import-from-slack).

### Before you start

You will need a server for hosting the bridge between Slack and Zulip. If you
do not otherwise run a server, XX or YY are easy options for setting one up.

All the commands below should be run on the server you will use for hosting the bridge.

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
   cd zulip/integrations/bridge_with_slack
   ```

1. Install the bridge dependencies in your virtualenv, by running:
    ```
    pip install -r requirements.txt
    ```

### Configure the bridge

1. In Zulip, [create a bot](/help/add-a-bot-or-integration), using **Generic bot**
   for the bot type. Download the bot's `zuliprc` configuration file to your
   computer.

1. [Subscribe the bot](/help/add-or-remove-users-from-a-stream) to the Zulip
   stream that will contain the mirror.

1. Make sure Websocket isn't blocked in the computer where you run this bridge.
   Test it at https://www.websocket.org/echo.html.

1. Make sure you are signed in to the Slack workspace you want to mirror.

1. Go to https://api.slack.com/apps?new_classic_app=1 and create a new classic
   app (note: must be a classic app). You can choose any descriptive name you
   want.

1. Once created, go to the left sidebar, and click "App Home," and then click
   "Add Legacy Bot User" Choose a bot username that will be put into
   bridge_with_slack_config.py in the username field in the Slack section, e.g.
   "zulip_mirror".

1. On the left sidebar, click "Install App" and then click "Install to
   Workspace." When successful, you should see a token that starts with
   "xoxb-..." (there is also a token that starts with "xoxp-..."; we need the
   "xoxb-..." one).

1. Subscribe the Slack bot to the relevant channel. You can do this by typing
   e.g. `/invite @zulip_mirror` in the relevant channel.

1. Fill up `bridge_with_slack_config.py` with the relevant information

1. Run the following command to start the Slack bridge:

    ```
    ./run-slack-bridge
    ```

If you have any questions, you can ask `@**Rein Zustand**` at https://chat.zulip.org.
