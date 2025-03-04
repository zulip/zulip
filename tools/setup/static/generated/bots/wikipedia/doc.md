# Wikipedia Bot

The Wikipedia bot is a Zulip bot that will search Wikipedia
for a provided keyword, and fetch a link to the associated
Wikipedia article. The link is returned to the same stream
it was @mentioned in

The Wikipedia bot uses the
[MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page)
to obtain the search results it returns

Using the Wikipedia bot is as simple as mentioning @\<wikipedia-bot-name\>,
followed by the keyword:

```
@<wikipedia-bot-name> <keyword>
```

## Setup

Beyond the typical obtaining of the zuliprc file, no extra setup is required to use the Wikipedia Bot

## Usage

1. ```@<wikipedia-bot-name> <keyword>``` -
fetches the link to the appropriate Wikipedia article.

    * For example, `@<wikipedia-bot-name> Zulip`
will return the link `https://en.wikipedia.org/wiki/Zulip`
<br>

2. If the keyword does not return an article link,
the bot will respond with an error message:

    `I am sorry. The search term you provided is not found`

<br>

3. If no keyword is provided, the bot will return the help text:

    ```Please enter your message after @mention-bot```
