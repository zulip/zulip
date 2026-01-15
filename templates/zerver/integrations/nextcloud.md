# Zulip Nextcloud integration

Send Nextcloud files in Zulip messages as uploaded files, public shared links,
or internal shared links.

{start_tabs}

## Configure Zulip

1. {!create-a-generic-bot.md!}

!!! tip "Using a bot"

    You can use your own Zulip account's API key for testing, but using a bot is
    recommended for improved security and more reliable channel discovery,
    especially on Zulip Cloud.

2. From **Settings → Personal settings → Bots**, copy the bot's **email address**
   and **API key**.

## Configure Nextcloud

1. Follow the instructions in the
   [Nextcloud App Store](https://apps.nextcloud.com/apps/integration_zulip)
   to install and enable the **Zulip Integration** app.

2. In Nextcloud, go to **User settings → Connected accounts**, and enter your
   **Zulip server URL**, **email address**, and **API key**.

{end_tabs}

Congrats, you're done! You should be able to send Nextcloud files to Zulip.

!!! tip "Channel discovery issues"

    If the **Conversation** dropdown shows "failed to load Zulip channels", ensure
    that you are using a bot account subscribed to the target streams, or a Zulip
    server that allows listing streams via the API.

### Related documentation

* [Zulip Integration in the Nextcloud App Store](https://apps.nextcloud.com/apps/integration_zulip)
