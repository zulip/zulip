# Import users and channels from Slack

{!follow-steps.md!} import users and channels from Slack to Zulip.

!!! warn ""
    **Note:** Please ensure that you have admin rights before importing users and channels from Slack.

1. Generate a Slack API token using Slack's [test token generator](https://api.slack.com/docs/oauth-test-tokens)
   to import all of the necessary data.

{!go-to-the.md!} [Your bots](/#settings/your-bots)
{!settings.md!}

3. Click on the **Show/change your API key** button.

4. Upon clicking the **Show/change your API key** button,
   you will be asked to confirm your identity by entering
   your password in the **Current password** field.

5. Click the **Get API Key** button and copy the generated API Key.

6. Fill all of the settings in `api/integrations/slack/zulip_slack_config.py`:

    * `SLACK_TOKEN` - the token from point number 1.

    * `ZULIP_USER` - the e-mail of the user (the user that API key was generated for).

    * `ZULIP_KEY` - the API key from point number 4.

    * `ZULIP_SITE` - the Zulip API server URI.

7. Install the `slacker` dependency using the command `pip install slacker`

8. Finally, run the script in your local Zulip directory using the command
`python api/integrations/slack/zulip_slack.py`

## Importing users from a different organization

If the users are not from the same organization, you should change your organization settings accordingly.

{!go-to-the.md!} [Organization settings](/#administration/organization-settings)
{!admin.md!}

2. Disable the **New users restricted to the following domains** option.
