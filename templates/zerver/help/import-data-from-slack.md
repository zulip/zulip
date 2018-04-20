# Import data from Slack (beta)

Starting with Zulip 1.8, Zulip supports importing data from Slack,
including users, channels, messages, attachments, avatars, custom
emoji, and emoji reactions.

!!! warn ""
    These instructions require shell access to the Zulip server. If you'd like
    to import a Slack organization into the hosted zulipchat.com service,
    contact support@zulipchat.com.

1. [Export your Slack data](https://my.slack.com/services/export). You will
   receive a zip file `slack_data.zip`.

    !!! warn ""
        **Note:** Only Slack owners and admins can export data from Slack.
        See Slack's
        [guide to data exports](https://get.slack.help/hc/en-us/articles/201658943-Export-data-and-message-history)
        for more information.

2. [Generate a Slack API token](https://api.slack.com/custom-integrations/legacy-tokens).

### Import into a new Zulip instance

Log in to your Zulip server as the `zulip` user. Run the following
commands, replacing `<token>` with the value generated above:

```
cd /home/zulip/deployments/current
./manage.py convert_slack_data slack_data.zip --token <token> --output converted_slack_data
./manage.py import --destroy-rebuild-database '' converted_slack_data
```

!!! warn ""
    **Warning:** This will destroy all existing data in your Zulip instance.

### Import into an existing Zulip instance

Log in to your Zulip server as the `zulip` user. Run the following
commands, replacing `<token>` with the value generated above, and
`<subdomain>` with the subdomain of the URL you'd like for your imported
Zulip organization.

```
cd /home/zulip/deployments/current
./manage.py convert_slack_data slack_data.zip --token <token> --output converted_slack_data
./manage.py import --import-into-nonempty <subdomain> converted_slack_data
```

## Logging in

Once the import completes, all your users will have accounts in your
new Zulip organization, but those accounts won't have passwords yet
(since for very good security reasons, passwords are not exported).
Your users will need to either authenticate using something like
Google auth, or start by resetting their passwords.

You can use the `./manage.py send_password_reset_email` command to
send password reset emails to your users.  We
recommend starting with sending one to yourself for testing:

```
./manage.py send_password_reset_email -u username@example.com
```

and then once you're ready, you can email them to everyone using e.g.
```
./manage.py send_password_reset_email -r '' --all-users
```

(replace `''` with your subdomain if you're using one).

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

- User phone numbers and custom user profile fields are not currently
  imported. We expect to address this in a future revision.

- Permission hierarchy:
    Slack's `Primary owner`, `owner`, and `admin` are mapped to Zulip's `Organization admin`.
    Slack's `Member`, `restricted`, and `ultra restricted` are mapped to regular Zulip users.
    `Channel creators` have no special permissions in Zulip.

- The "joined #channel_name" messages are not imported.

- The import tool does not support simultaneous bold and italic
  formatting of a word; we expect to address this in a future revision.
