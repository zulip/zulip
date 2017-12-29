# Import users and channels from Slack

{!follow-steps.md!} import users and channels from Slack to Zulip.

!!! warn ""
    **Note:** Please ensure that you have admin rights before importing users and channels from Slack.

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
