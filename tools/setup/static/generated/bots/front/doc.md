# Front Bot

## Setup

1. Go to the `Setting` of your Front app.
2. Copy the `JSON Web Token` from `Plugins & API` → `API`.
3. Replace `<api_key>` in `zulip_bots/bots/front/front.conf` with `JSON
Web Token`.

## Usage

![](assets/usage.png)

The name of the topic, from which you call the bot, must contain the ID of
the corresponding Front conversation. If you have received notifications
from this conversation using Front incoming webhook, you can use the topic
it has created.
