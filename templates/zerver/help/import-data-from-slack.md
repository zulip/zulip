# Import data from Slack

{!follow-steps.md!} import users, channels, and messages from Slack to Zulip.

!!! warn ""
    **Note:** Please ensure that you have admin rights before importing data from Slack.

1. Export your team's data and message history by visiting the **Export Data**
   page, https://my.slack.com/services/export. You will receive a zip file
   `slack_data.zip`. Currently we only support standard export. See
   https://get.slack.help/hc/en-us/articles/201658943-Export-data-and-message-history
   for more detail on this step.
2. Convert the zip file `slack_data.zip` to Zulip export format using the
   command `./manage.py convert_slack_data <slack_zip_file> <organization_name> --output <output_dir>`.
3. Import the converted data. If you are importing into an existing database,
   run the command `./manage.py import --import-into-nonempty <output_dit>`,
   otherwise, if you are importing into a new Zulip instance, run the command
   `./manage.py import --destory-rebuild-database <output_dir>`.

## Importing users from a different organization

If the users are not from the same organization, you should change your organization settings accordingly.

{!go-to-the.md!} [Organization settings](/#administration/organization-settings)
{!admin.md!}

2. Disable the **Restrict new users to the following email domains** option.

## Elements that are not mapped one to one

- Non-Gravatar-based avatar. This is not yet implemented by the conversion script.
- Attachment. This is not yet implemented by the conversion script.
  Additionally, pinning attachment to a channel is not yet supported by Zulip.
- Reactions. This is not yet implemented by the conversion script.
- Message edit history. We only keep the latest revision of an edited message.
- Permission hierarchy. They are mapped as follows
  * `Primary owner` and `owner` are mapped to `organization admin`.
  * `Admin` is mapped to `staff`.
  * `Member`, `restricted`, and `ultra restricted` are mapped to regular user.
  * `Channel creators` have no special permission in Zulip.
- Simultaneous bold and italic formatting of a word. This is not yet supported
  by Zulip's backend markdown.
- The "joined #channel_name" messages. They are intentionally removed because
  they are spammy.
- Zulip does not support default channels which can't be unsubscribed from, but
  it does include a list of streams where everyone is subscribed to by default
  when they register.
