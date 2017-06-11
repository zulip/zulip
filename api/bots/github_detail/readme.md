# GitHub detail bot

This bot links and details issues and pull requests.
To use it @-mention the bot then type an id:
Ids can be specified in three different forms:
- Id only: `#2000`
- Repository and id: `zulip#2000`
- Owner, repository and id `zulip/zulip#2000`

The id can occur at any time in the message. You
can also mention multiple ids in a single message. For example:

`@**GitHub Detail Bot** find me #5176 and zulip/zulip#4534 .`

You can configure a default owner and repository.
The configuration file should be located at `api/bots/github_detail/github_detail.conf`.
It should look like this:
```ini
[github_detail]
owner = <repository owner>
repo = <repository name>
```
