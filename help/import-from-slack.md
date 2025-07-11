# Import from Slack

{!import-workspace-to-zulip.md!}

## Import process overview

To import your Slack organization into Zulip, you will need to take the
following steps, which are described in more detail below:

{start_tabs}

1. [Export your Slack data](#export-your-slack-data).

1. [Import your Slack data into Zulip](#import-your-data-into-zulip).

1. [Clean up](#clean-up-after-the-slack-export) after the Slack export.

1. [Get your organization started with Zulip](#get-your-organization-started-with-zulip)!

{end_tabs}

## Import your organization from Slack into Zulip
<!-- Update link in slack_import.html when changing title below. -->
### Export your Slack data

Slack's [data export
service](https://slack.com/services/export) allows you to
export all public channel messages, **including older messages that may no
longer be searchable** under your Slack plan.

Unfortunately, Slack [only
allows](https://slack.com/help/articles/201658943-Export-your-workspace-data)
workspaces that are on the **Business+** or **Enterprise Grid** plans
to export private channels and direct messages. Slack's support has
confirmed this policy as of August 2022.

Owners of **Business+** or **Enterprise Grid** workspaces can [request
special
access](https://slack.com/help/articles/204897248-Guide-to-Slack-import-and-export-tools#options-by-plan)
in order to export direct message data.

#### Export message history

{start_tabs}

1. Make sure that you are an owner or admin of your Slack
   workspace. If you are one, the Slack web application will display
   that in your profile, in a banner covering the bottom of your
   avatar.

1. [Export your Slack message history](https://my.slack.com/services/export).
   You should be able to download a `zip` file with your data a few minutes
   after you start the export process.

{end_tabs}

#### Export user data and custom emoji

{start_tabs}

1. Make sure that you are an owner or admin of your Slack
   workspace. If you are one, the Slack web application will display
   that in your profile, in a banner covering the bottom of your
   avatar.

1. [Create a new Slack app](https://api.slack.com/apps). Choose the "From
   scratch" creation option.

1. [Create a
   bot user](https://api.slack.com/authentication/basics#scopes),
   following the instructions to add the following OAuth scopes to your bot:
    - `emoji:read`
    - `users:read`
    - `users:read.email`
    - `team:read`

1. [Install your new app](https://api.slack.com/authentication/basics#installing)
   to your Slack workspace.

1. You will immediately see a **Bot User OAuth Token**, which is a long
   string of numbers and characters starting with `xoxb-`. Copy this token. It
   grants access to download user and emoji data from your Slack workspace.

!!! warn ""

    You may also come across a token starting with `xoxe-`. This token cannot
    be used for the Slack export process.

{end_tabs}

### Import your data into Zulip

{!import-your-data-into-zulip.md!}

{start_tabs}

{tab|zulip-cloud}

{!import-into-a-zulip-cloud-organization.md!}

1. Your Slack **Bot User OAuth Token**, which will be a long
   string of numbers and characters starting with `xoxb-`.

{!import-zulip-cloud-organization-warning.md!}

{tab|self-hosting}

{!import-into-a-self-hosted-zulip-server.md!}

1. To import into an organization hosted on the root domain
   (`EXTERNAL_HOST`) of the Zulip installation, run the following
   commands, replacing `<token>` with your Slack **Bot User OAuth Token**.

    {!import-self-hosted-server-tips.md!}

    ```
    cd /home/zulip/deployments/current
    ./scripts/stop-server
    ./manage.py convert_slack_data /tmp/slack_data.zip --token <token> --output /tmp/converted_slack_data
    ./manage.py import '' /tmp/converted_slack_data
    ./scripts/start-server
    ```

    Alternatively, to import into a custom subdomain, run:

    ```
    cd /home/zulip/deployments/current
    ./scripts/stop-server
    ./manage.py convert_slack_data /tmp/slack_data.zip --token <token> --output /tmp/converted_slack_data
    ./manage.py import <subdomain> /tmp/converted_slack_data
    ./scripts/start-server
    ```

1. Follow [step 4](https://zulip.readthedocs.io/en/stable/production/install.html#step-4-configure-and-use)
   of the guide for [installing a new Zulip
   server](https://zulip.readthedocs.io/en/stable/production/install.html).

{end_tabs}

#### Import details

Whether you are using Zulip Cloud or self-hosting Zulip, here are few notes to keep
in mind about the import process:

- Slack does not export workspace settings, so you will need to [configure
  the settings for your Zulip organization](/help/customize-organization-settings).
  This includes settings like [email
  visibility](/help/configure-email-visibility),
  [message editing permissions](/help/restrict-message-editing-and-deletion),
  and [how users can join your organization](/help/restrict-account-creation).

- Slack does not export user settings, so users in your organization may want to
  [customize their account settings](/help/getting-started-with-zulip).

- Slack's user roles are mapped to Zulip's [user
  roles](/help/user-roles) in the following way:

| Slack role              | Zulip role    |
|-------------------------|---------------|
| Workspace Primary Owner | Owner         |
| Workspace Owner         | Owner         |
| Workspace Admin         | Administrator |
| Member                  | Member        |
| Single Channel Guest    | Guest         |
| Multi Channel Guest     | Guest         |
| Channel creator         | none          |

- Slack threads are imported as topics with names that include snippets of the
  original message, such as "2023-05-30 Hi, can anyone reply if you're o…".

- Message edit history and `@user joined #channel_name` messages are not imported.

## Clean up after the Slack export

Once your organization has been successfully imported in to Zulip, you should
delete [the Slack app](https://api.slack.com/apps) that you created in order to
[export your Slack data](#export-your-slack-data).  This will prevent the OAuth
token from being used to access your Slack workspace in the future.

## Get your organization started with Zulip

{!import-get-your-organization-started.md!}

!!! tip ""

    Zulip's [Slack-compatible incoming webhook](/integrations/doc/slack_incoming)
    makes it easy to migrate integrations.

## Decide how users will log in

{!import-how-users-will-log-in.md!}

## Related articles

* [Choosing between Zulip Cloud and self-hosting](/help/zulip-cloud-or-self-hosting)
* [Moving to Zulip](/help/moving-to-zulip)
* [Slack-compatible incoming webhook](/integrations/doc/slack_incoming)
* [Getting started with Zulip](/help/getting-started-with-zulip)
