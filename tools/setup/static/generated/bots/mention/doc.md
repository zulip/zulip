# Mention bot

The Mention bot is a Zulip bot that can fetch Mentions associated with
a given keyword from the web using [Mention](https://mention.com/en/).

To use the Mention bot, you can simply call it with `@<botname>` followed
by a keyword, like so:

```
@Mention Apple
```

## Setup

Before you can proceed further, you'll need to go to the
[Mention Dev](https://dev.mention.com/login), and get a
Mention API Access Token.

1. Login.
2. Enter the **App Name**, **Description**, **Website**, and **Redirect uris**. In this version, there
is no actual use of the Redirect Uri and Website.
3. After accepting the agreement, click on **Create New App**.
4. And you're done! You should now have an Access Token.
5. Open up `zulip_bots/bots/mention/mention.conf` in an editor and
   change the value of the `<access_token>` attribute to the Access Token
   you generated above.

## Usage
`@Mention <keyword>` - This command will fetch the most recent 20
mentions of the keyword on the web (Limitations of a free account).
Example:
![](assets/mentions_demo.png)
