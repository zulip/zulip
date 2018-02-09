# Import data from Slack

{!follow-steps.md!} import users, channels, and messages from Slack to Zulip.

!!! warn ""
    **Note:** Please ensure that you have admin rights before importing data from Slack.

1. Export your team's data and message history by visiting the **Export Data**
   page, https://my.slack.com/services/export. You will receive a zip file
   `slack_data.zip`. Currently we only support standard export. See
   https://get.slack.help/hc/en-us/articles/201658943-Export-data-and-message-history
   for more detail on this step.
2. Generate a Slack API token using Slack's test
   [token generator](https://api.slack.com/custom-integrations/legacy-tokens)
   to import all of the necessary data. We use this as current Slack exports don't
   include user's email data, however, we still get that data from Slack's older
   method of legacy tokens.
   **Note:** Once Slack starts including user emails in the exports,
   this extra step of using legacy tokens to get user data would no longer be
   necessary.
3. Convert the zip file `slack_data.zip` to Zulip export format using the command
   `./manage.py convert_slack_data <slack_zip_file> <organization_name> --token <token> --output <output_dir>`.
4. Import the converted data. If you are importing into an existing database,
   run the command `./manage.py import --import-into-nonempty <output_dir>`,
   otherwise, if you are importing into a new Zulip instance, run the command
   `./manage.py import --destory-rebuild-database <output_dir>`.

## Importing users from a different organization

If the users are not from the same organization, you should change your organization settings accordingly.

{!go-to-the.md!} [Organization settings](/#administration/organization-settings)
{!admin.md!}

2. Disable the **Restrict new users to the following email domains** option.

## Slack data elements that are not translated to a corresponding Zulip element

- Non-Gravatar-based avatar. This is not yet implemented by the conversion script.
- Attachment. This is not yet implemented by the conversion script.
  (Additionally, Zulip doesn't have an analog of Slack's "pinned
  attachment" feature).
- Reactions. This is not yet implemented by the conversion script.
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
