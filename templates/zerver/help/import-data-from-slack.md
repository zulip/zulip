# Import data from Slack

{!follow-steps.md!} import data from Slack to Zulip. We support export of users, channels,
messages, attachments, avatars and emojis (both standard and custom).

!!! warn ""
    **Note:** Please ensure that you have admin rights before importing data from Slack.

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
`./manage.py convert_slack_data <zip_file> <organization_name> --token <token> --output <output_dir>`.
This would generate a data file `output_dir` in Zulip's format.

4. Import the converted data into a Zulip using the command
`./manage.py import --import-into-nonempty <output_dir>`

**Note:** We only support Slack's standard plan.
See [Slack documentation](https://get.slack.help/hc/en-us/articles/204897248-Guide-to-Slack-import-and-export-tools)
for more details.

## Importing users from a different organization

If the users are not from the same organization, you should change your organization settings accordingly.

{!go-to-the.md!} [Organization settings](/#administration/organization-settings)
{!admin.md!}

2. Disable the **Restrict new users to the following email domains** option.

## Slack data elements that are not translated to a corresponding Zulip element

- Zulip doesn't have an analog of Slack's "pinned
  attachment" feature.
- Message edit history. We only transfer the latest revision of an edited message.
- Permission hierarchy. They are mapped as follows
  * `Primary owner`, `owner`, and `Admin` are mapped to `organization admin`.
  * `Member`, `restricted`, and `ultra restricted` are mapped to regular user.
  * `Channel creators` have no special permission in Zulip.
- Simultaneous bold and italic formatting of a word. This is not yet supported
  by Zulip's backend markdown.
- The "joined #channel_name" messages. They are intentionally removed because
  they are spammy.
- Zulip's "default streams" work slightly differently from Slack's
  "Default channels" -- new users are automatically subscribed, but
  users can still unsusbcribe from them.
- As user phone number and skype username are not stored in Zulip, they
  are not preserved during the conversion.
