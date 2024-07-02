# idonethis bot

The idonethis bot is a Zulip bot which allows interaction with [idonethis](https://idonethis.com/)
through Zulip. It can peform actions such as viewing teams, list entries and creating entries.

To use the bot simply @-mention the bot followed by a specific command. See the usage section
below for a list of available commands.

## Setup

Before proceeding further, ensure you have an idonethis account.

 1. Go to [your idonethis settings](https://beta.idonethis.com/u/settings), scroll down
and copy your API token.
 2. Open up `zulip_bots/bots/idonethis/idonethis.conf` in your favorite editor, and change
`api_key` to your API token.
 3. Optionally, change the `default_team` value to your default team for creating new messages.
If this is not specified, a team will be required to be manually specified every time an entry is created.

Run this bot as described [here](https://zulipchat.com/api/running-bots#running-a-bot).

## Usage

`<team>` can either be the name or ID of a team.

 * `@mention help` view this help message.
    ![](/static/generated/bots/idonethis/assets/idonethis-help.png)
 * `@mention teams list` or `@mention list teams`
    List all the teams.
    ![](/static/generated/bots/idonethis/assets/idonethis-list-teams.png)
 * `@mention team info <team>`.
    Show information about one `<team>`.
    ![](/static/generated/bots/idonethis/assets/idonethis-team-info.png)
 * `@mention entries list` or `@mention list entries`.
    List entries from any team
    ![](/static/generated/bots/idonethis/assets/idonethis-entries-all-teams.png)
 * `@mention entries list <team>` or `@mention list entries <team>`
    List all entries from `<team>`.
    ![](/static/generated/bots/idonethis/assets/idonethis-list-entries-specific-team.png)
 * `@mention entries create` or `@mention new entry` or `@mention create entry`
    or `@mention new entry` or `@mention i did`
    Create a new entry. Optionally supply `--team=<team>` for teams with no spaces or `"--team=<team>"`
    for teams with spaces. For example `@mention i did "--team=product team" something` will create a
    new entry `something` for the product team.
    ![](/static/generated/bots/idonethis/assets/idonethis-new-entry.png)
    ![](/static/generated/bots/idonethis/assets/idonethis-new-entry-specific-team.png)
