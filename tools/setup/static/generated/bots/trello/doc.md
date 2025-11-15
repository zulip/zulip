# Trello bot

The Trello bot is a Zulip bot that enables interaction with Trello using the
[Trello API](https://developers.trello.com).

To use the Trello bot, you can simply call it with `@<botname>` followed
by a command, like so:

```
@Trello help
```

## Setup

Before usage, you will need to configure the bot by putting the value of the `<api_key>`,
`<access_token>`, and `<user_name>` in the config file.
To do this, follow the given steps:

1. Go to [this]( https://trello.com/app-key) link after logging in at
[Trello]( https://trello.com/).
2. Generate an `access_token` and note it down. Continue to get your
`api_key`.
3. Go to your profile page in Trello and note down your `username`.
4. Open up `zulip_bots/bots/trello/trello.conf` in an editor and
change the values of the `<api_key>`, `<access_token>`, and `<user_name>`
attributes to the corresponding noted values.

## Developer Notes

Be sure to add the additional commands and their descriptions to the `supported_commands`
list in `trello.py` so that they can be displayed with the other available commands using
`@<botname> list-commands`. Also modify the `test_list_commands_command` in
`test_trello.py`.

## Usage

`@Trello list-commands` - This command gives a list of all available commands along with
short descriptions.

Example:
![](assets/list_commands.png)
