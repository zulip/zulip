# Flock Bot

With [Flock](https://flock.com/) bot, you can send messages to any of your
 flock contact without having to leave Zulip.

Sending messages to a user is quite easy, syntax is:
`@botname recipient_name: hello`
where `recipient_name` is name of recipient and `hello` is the sample message.

## Configuration

1. Before running Flock bot, you'll need a `token`. In order to get `token`,
 Go to [Flock apps](https://dev.flock.com/apps) and create an app.
   After successful installation, you'll get an `token` in response from servers.

1. Once you have `token`, you should supply it in `flock.conf` file.

## Usage

Run this bot as described in
 [here](https://zulipchat.com/api/running-bots#running-a-bot).

You can use this bot in one easy step:

`@botname recipient_firstName: message`

For help, do `@botname help`.
