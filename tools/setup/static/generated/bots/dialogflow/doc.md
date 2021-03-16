# DialogFlow bot
This bot allows users to easily add their own DialogFlow bots to zulip.

## Setup
To add your DialogFlow bot:
Add the V1 Client access token from your agent's settings in the DialogFlow console to
`dialogflow.conf`, and write a short sentence describing what your bot does in the same file
as `bot_info`.

## Usage

Run this bot as described
[here](https://zulipchat.com/api/running-bots#running-a-bot).

Mention the bot in order to say things to it.

For example: `@weather What is the weather today?`


## Limitations
When creating your DialogFlow bot, please consider these things:

- Empty input will not be sent to the bot.
- Only text can be sent to, and recieved from the bot.
