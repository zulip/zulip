# GitHub detail bot
This bot links and details issues and pull requests.
To use it username mention the bot then type an id:
Ids can be specified in three different forms:
- Id only: `#2000`
- Repository and id: `zulip#2000`
- Owner, repository and id `zulip/zulip#2000`

Both the username mention and the id can occur at any time in the message. You
can also mention multiple ids in a single message.

The bot *requires* a default owner and repository to be configured.
The configuration file should be located at `~/.contrib_bots/github_detail.ini`.
It should look like this:
```ini
[GitHub]
owner = <repository_owner>
repo = <repository>
```
If you don't want a default repository you can define one that doesn't exist, the bot
will fail silently.

The bot won't reply to any other bots to avoid infinite loops.

Zulip also has a realm feature which will show information about linked sites.
Because of this the bot escapes it's links. Once issue
[#2968](https://github.com/zulip/zulip/issues/2968) is resolved this can be
changed.
