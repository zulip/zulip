# Import from Slack (beta)

Starting with Zulip 1.8, Zulip supports importing data from Slack,
including users, channels, messages, attachments, avatars, custom
emoji, and emoji reactions.

**Note:** You can only import a Slack workspace as a new Zulip
organization. In particular, you cannot use this tool to import from Slack
into an existing Zulip organization.

## Import from Slack

First, export your data from Slack.

1. [Export your Slack data](https://my.slack.com/services/export). You will
   receive a zip file `slack_data.zip`.

    !!! warn ""
        **Note:** Only Slack owners and admins can export data from Slack.
        See Slack's
        [guide to data exports](https://get.slack.help/hc/en-us/articles/201658943-Export-data-and-message-history)
        for more information.

2. [Generate a Slack API token](https://api.slack.com/custom-integrations/legacy-tokens).

### Import into zulipchat.com

Email support@zulipchat.com with `slack_data.zip`, the Slack API token
generated above, and your desired subdomain. Your imported organization will
be hosted at `<subdomain>.zulipchat.com`.

If you've already created a test organization at
`<subdomain>.zulipchat.com`, let us know, and we can rename the old
organization first.

### Import into a new Zulip server

Because the Slack import tool is very new, we recommend first
upgrading your new Zulip server to the latest `master` branch,
using [upgrade-zulip-from-git][upgrade-zulip-from-git] to avoid
bugs in the earliest versions of the Slack import tool.

Log in to a shell on your Zulip server as the `zulip` user. Run the
following commands, replacing `<token>` with the value generated
above:

```
cd /home/zulip/deployments/current
./manage.py convert_slack_data slack_data.zip --token <token> --output converted_slack_data
./manage.py import --destroy-rebuild-database '' converted_slack_data
```

!!! warn ""
    **Warning:** This will destroy all existing data in your Zulip server

### Import into an existing Zulip server

If you already have some organizations hosted on your Zulip server,
and want to add import your Slack data as a new Zulip organization,
you can use the following procedure.

Log in to your Zulip server as the `zulip` user. Run the following
commands, replacing `<token>` with the value generated above, and
`<subdomain>` with the subdomain of the URL you'd like for your imported
Zulip organization.

```
cd /home/zulip/deployments/current
./manage.py convert_slack_data slack_data.zip --token <token> --output converted_slack_data
./manage.py import --import-into-nonempty <subdomain> converted_slack_data
```

{!import-login.md!}

## Caveats

- Slack doesn't export private channels or direct messages unless you pay
  for Slack Plus or contact Slack support. See
  [Slack's documentation](https://get.slack.help/hc/en-us/articles/204897248-Guide-to-Slack-import-and-export-tools)
  for more details.

- (Slack Plus import) Private channels and direct messages are currently
  not imported. We expect to address this in a future revision.

- (Slack Plus import) Message edit history is currently not imported.

- Slack doesn't export user settings or organization settings, so
  you'll need to configure these manually.

- Permission hierarchy:
    Slack's `Primary owner`, `owner`, and `admin` are mapped to Zulip's `Organization admin`.
    Slack's `Member`, `restricted`, and `ultra restricted` are mapped to regular Zulip users.
    `Channel creators` have no special permissions in Zulip.

- The "joined #channel_name" messages are not imported.

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/maintain-secure-upgrade.html#upgrading-from-a-git-repository
