# StackOverflow Bot

The StackOverflow bot is a Zulip bot that will search Stackoverflow
for a provided set of keywords or a question, and fetch a link to the associated
query. The link is returned to the same stream
it was @mentioned in

The Stackoverflow bot uses the
[StackExchange API](http://api.stackexchange.com/docs)
to obtain the search results it returns

Using the StackOverflow bot is as simple as mentioning @\<stackoverflow-bot-name\>,
followed by the query:

```
@<stackoverflow-bot-name> <query>
```

## Setup

Beyond the typical obtaining of the zuliprc file, no extra setup is required to use the StackOverflow Bot

## Usage

1. ```@<stackoverflow-bot-name> <query>``` -
fetches the link to the appropriate StackOverflow questions.

    * For example, `@<stackoverflow-bot-name> rest api`
will return the links having questions related to rest api.
<br>

2. If there are no questions related to the query,
the bot will respond with an error message:

    `I am sorry. The search query you provided is does not have any related results.`

<br>

3. If no query is provided, the bot will return the help text:

    ```Please enter your message after @mention-bot```
