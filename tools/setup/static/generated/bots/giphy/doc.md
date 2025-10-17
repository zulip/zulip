# GIPHY bot

The GIPHY bot is a Zulip bot that can fetch a GIF associated with
a given keyword from [GIPHY](https://giphy.com/).

To use the GIPHY bot, you can simply call it with `@Giphy` followed
by a keyword, like so:

```
@Giphy hello
```

## Setup

Before you can proceed further, you'll need to go to the
[GIPHY Developers](https://developers.giphy.com/), and get a
GIPHY API key.

1. Click on the **Create an App** button on the top right corner.
2. Click on **Create an App** under the **Your Apps** section.
3. Enter a name and a description for your app and click on
   **Create New App**.
4. And you're done! You should now have a GIPHY API key.
5. Open up `zulip_bots/bots/giphy/giphy.conf` in an editor and
   and change the value of the `key` attribute to the API key
   you generated above.

Run this bot as described in [here](https://zulipchat.com/api/running-bots#running-a-bot).

## Usage

1. `@Giphy <keyword` - This command will fetch a GIF associated
   with the given keyword. Example usage: `@Giphy hello`:
   ![](/static/generated/bots/giphy/assets/giphy-gif-found.png)

2. If a GIF can't be found for a given keyword, the bot will
   respond with an error message:
   ![](/static/generated/bots/giphy/assets/giphy-gif-not-found.png)

3. If there's a connection error, the bot will respond with an
   error message:
   ![](/static/generated/bots/giphy/assets/giphy-connection-error.png)
