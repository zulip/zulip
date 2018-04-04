# Import data from Slack

{!follow-steps.md!} import data from Slack to Zulip. We support
importing data from Slack, including users, channels, messages,
attachments, avatars, custom emoji, and emoji reactions.

!!! warn ""
    **Note:** You need administrative rights to the Slack workspace to export data from Slack.

{!go-to-the.md!} [Slack's export page](https://my.slack.com/services/export) to get your
team's zipped data file.

2. Generate a Slack API legacy token using Slack's
[token generator](https://api.slack.com/custom-integrations/legacy-tokens)
to import all of the necessary data. We use this as current Slack exports don't
include user's email data, however, we still get that data from Slack's older
method of legacy tokens.
**Note:** Once Slack starts including user emails in the exports,
this extra step of using legacy tokens to get user data would no longer be
necessary.

3. Convert the zip file to Zulip export format using the command
`./manage.py convert_slack_data <zip_file> <organization_name> --token
<token> --output <output_dir>`.  This would generate a data file
`output_dir` in Zulip's standard data import format.

4. Import the converted data into a Zulip using the command
`./manage.py import --import-into-nonempty <output_dir>`

!!! tip ""
    These instructions require shell access to the Zulip server.
    If you'd like to import a Slack organization into the hosted
    zulipchat.com service, contact support@zulipchat.com.

## Slack data elements that are not directly translated

- Slack's data exports only include public channels and messages to
public channels unless you pay for their Plus plan or contact Slack
support.  See
[Slack documentation](https://get.slack.help/hc/en-us/articles/204897248-Guide-to-Slack-import-and-export-tools)
for more details.
- The Slack->Zulip converter does not yet support private channels and
  private messages.  We expect to address this in a future revision.
- Message edit history.  Slack only exports the latest revision of edited messages.
- Permission hierarchy. They are mapped as follows
    * Slack's **Primary Owner**, **Workspace Owner**, and **Workspace
      Admin** users are mapped to Zulip organization administrators.
    * Slack's **Member**, **Multi-Channel Guest**, and
      **Single-Channel Guest** users are mapped to regular Zulip users.
    * Slack's **Channel Creators** have no special permission in Zulip.
- Zulip's "default streams" work slightly differently from Slack's
  "Default channels" -- new users are automatically subscribed, but
  users can still unsusbcribe from them.
- Slack's phone number and skype username fields are not transferred
  to Zulip.  We expect in a future version to convert these to custom
  profile fields.
- Zulip doesn't have an analog of Slack's "pinned attachments" feature.
- Simultaneous bold and italic formatting of a word. This is not yet supported
  by Zulip's backend markdown.
- Slack's "joined #channel_name" notifications are intentionally not
  transferred because they are spammy.
- Slack's data export tools don't contain details about
  organization-level settings, so you'll need to configure the Zulip
  organization settings manually.
