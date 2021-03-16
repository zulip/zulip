# YouTube bot

The YouTube bot is a Zulip bot that can search for videos from [YouTube](https://www.youtube.com/).

To use the YouTube bot, you can simply call it with `@YouTube` followed
by a keyword(s), like so:

```
@YouTube funny cats
```

## Setup

Before starting you will need a Developer's API key to run the bot.
To obtain a API key, follow the following steps :

 1. Create a project in the [Google Developers Console](https://console.developers.google.com/)

 2. Open the [API Library](https://console.developers.google.com/apis/library?project=_)
    in the Google Developers Console. If prompted, select a project or create a new one.
    In the list of APIs, select `Youtube Data API v3` and  make sure it is enabled .

 3. Open the [Credentials](https://console.developers.google.com/apis/credentials?project=_) page.

 4. In the Credentials page , select *Create Credentials > API key*

 5. Open `zulip_bots/bots/youtube/youtube.conf` in an editor and
    and change the value of the `key` attribute to the API key
    you generated above.

 6. And that's it ! See Configuration section on configuring the bot.

## Configuration

This section explains the usage of options `youtube.conf` file in configuring the bot.
 - `key` - Used for setting the API key. See the above section on setting up the bot.

 - `number_of_results` - The maximum number of videos to show when searching
   for a list of videos with the `@YouTube list <keyword>` command.

 - `video_region` - The location to be used for searching.
   The bot shows only the videos that are available in the given `<video_region>`

Run this bot as described in [here](https://zulipchat.com/api/running-bots#running-a-bot).

## Usage

1. `@YouTube <keyword>`
  - This command search YouTube with the given keyword and gives the top result of the search.
    This can also be done with the command `@YouTube top <keyword>`
  - Example usage: `@YouTube funny cats` , `@YouTube top funny dogs`
    ![](/static/generated/bots/youtube/assets/youtube-search.png)

2. `@YouTube list <keyword>`
  - This command search YouTube with the given keyword and gives a list of videos associated with the keyword.
  - Example usage: `@YouTube list origami`
    ![](/static/generated/bots/youtube/assets/youtube-list.png)

2. If a video can't be found for a given keyword, the bot will
   respond with an error message
   ![](/static/generated/bots/youtube/assets/youtube-not-found.png)

3. If there's a error while searching, the bot will respond with an
   error message
   ![](/static/generated/bots/youtube/assets/youtube-error.png)
