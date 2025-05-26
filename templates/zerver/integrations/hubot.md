# Zulip Hubot Integration

Use Hubot to execute scripts and commands within Zulip!

{start_tabs}

1. Follow the [**Getting Started with Hubot**][getting-started] guide
   to create your Hubot. You'll have a new directory from which `bin/hubot`
   starts a vanilla Hubot instance with the shell backend.

1. In your Hubot's directory, install the Zulip adapter by running:

      `npm install --save hubot-zulip`

1. {!create-a-generic-bot.md!}

1. Hubot uses the following environment variables, set them using the
   information of the bot you created, by running:

    ```
    export HUBOT_ZULIP_SITE="{{ zulip_url }}"
    export HUBOT_ZULIP_BOT="hubot-bot@{{ zulip_url }}"
    export HUBOT_ZULIP_API_KEY="0123456789abcdef0123456789abcdef"
    ```

1. Run Hubot:

    `bin/hubot --adapter zulip --name "<bot username>"`

!!! tip ""

    Hubot automatically listens for commands on all public channels. Private
    channels require an invitation. Hubot's access can be
    [configured](#configuration-options).

{end_tabs}

To test your Hubot installation, send it an @-notification with a
basic command, e.g., `@Hubot pug me`, which should produce a
result like this:

![Hubot message](/static/images/integrations/hubot/001.png)

### Configuration options

* To make Hubot listen only on the channels that it is subscribed to, run:

     `export HUBOT_ZULIP_ONLY_SUBSCRIBED_STREAMS`

### Related documentation

* [GitHub repository for Zulip Hubot adapter][hubot-zulip]

* Zulip Integrations using Hubot: [Assembla](/integrations/doc/assembla) |
  [Bonusly](/integrations/doc/bonusly) |
  [Chartbeat](/integrations/doc/chartbeat) |
  [Dark Sky](/integrations/doc/darksky) |
  [Instagram](/integrations/doc/instagram) |
  [Google Translate](/integrations/doc/google-translate) |
  [MailChimp](/integrations/doc/mailchimp) |
  [YouTube](/integrations/doc/youtube)

* [Other Hubot adapters][other-adapters]

[hubot-zulip]: https://github.com/zulip/hubot-zulip
[getting-started]: https://hubot.github.com/docs/#getting-started-with-hubot
[other-adapters]: https://github.com/search?q=topic%3Ahubot-adapter&type=Repositories
