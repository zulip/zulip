# Zulip Hubot Integration

{start_tabs}

1. Follow the **Getting Started with Hubot** section of the
   [Hubot README][getting-started] to create your Hubot. You'll have a new
   directory from which `bin/hubot` starts a vanilla Hubot instance with
   the shell backend.

1. In your Hubot's directory, install the Zulip adapter by running:

      `npm install --save hubot-zulip`

1. {!create-a-generic-bot.md!}
   Note its name, email address and API key, as you will need them next.

1. To run Hubot locally, set the following environment
   variables by running:

    ```
    export HUBOT_ZULIP_SITE="{{ api_url }}"
    export HUBOT_ZULIP_BOT="hubot-bot@example.com"
    export HUBOT_ZULIP_API_KEY="<your_key>"
    ```

    Then, run:

    `bin/hubot --adapter zulip --name "<bot username>"`

!!! tip ""

    Hubot automatically listens for commands on all public channels. Private
    channels require an invitation.

{end_tabs}

To test your Hubot installation, send it an @-notification with a
basic command, e.g., `@Hubot pug me`, which should produce a
result like this:

![Hubot message](/static/images/integrations/hubot/001.png)

### Related documentation

* [Source code for the hubot-zulip adapter is available on GitHub][1]
[1]: https://github.com/zulip/hubot-zulip

* [Check out all integrations available via Hubot][2]
[2]: https://github.com/hubot-scripts

[getting-started]: https://hubot.github.com/docs/#getting-started-with-hubot
