xkcd bot is a Zulip bot that can fetch a comic strip from xkcd. To use
the xkcd bot, you can simply call it with `@xkcd` followed by a command,
like so:

```
@xkcd <command>
```

Run this bot as described in [here](https://zulipchat.com/api/running-bots#running-a-bot).

### Usage

The xkcd bot has four commands:

1. `help` - This command is used to list all commands that can be used
   with this bot. Example usage: `@xkcd help`:
   ![](/static/generated/bots/xkcd/assets/xkcd-help.png)

2. `latest` - This command is used to fetch the latest comic strip from
   xkcd. Example usage: `@xkcd latest`:
   ![](/static/generated/bots/xkcd/assets/xkcd-latest.png)

3. `random`- This command is used to fetch a random comic strip from xkcd.
   Example usage: `@xkcd random`:
   ![](/static/generated/bots/xkcd/assets/xkcd-random.png)

4. `<comic_id>` - To fetch a comic strip based on ID, you can supply the
   ID to the bot as a parameter (`@xkcd <comic_id>`). For example, if you
   want to fetch a comic strip with ID 1234, type `@xkcd 1234`:
   ![](/static/generated/bots/xkcd/assets/xkcd-specific-id.png)
   If the ID requested doesn't exist, the bot will post a message that
   the comic strip associated with that ID is not available, like so:
   ![](/static/generated/bots/xkcd/assets/xkcd-wrong-id.png)

5. If you type a command that isn't recognized by the bot, it will respond
   the information printed by the `@xkcd help` command:
   ![](/static/generated/bots/xkcd/assets/xkcd-wrong-command.png)
