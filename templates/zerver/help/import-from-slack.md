# Import from Slack

You can import your Slack organization into Zulip. It's a great way to preserve
your organization's history when you migrate from Slack to Zulip, and to make
the transition easy for the members of your organization.

The import will include your organization's:

* **Name** and **Logo**
* **Message history**, including attachments and emoji reactions
* **Users**, including names, emails, roles, avatars, time zones, and custom profile fields
* **Channels**, including all user subscriptions
* **Custom emoji**

## Import process overview

To import your Slack organization into Zulip, you will need to take the
following steps, which are described in more detail below:

{start_tabs}

1. [Export your Slack data](/help/import-from-slack#export-your-slack-data).

2. [Import you Slack data into
   Zulip](/help/import-from-slack#import-your-data-into-zulip).

3. [Clean up](/help/import-from-slack#clean-up-after-the-slack-export) after the Slack export.

4. [Get your organization started with Zulip](/help/import-from-slack#get-your-organization-started-with-zulip)!

{end_tabs}

## Import your organization from Slack into Zulip

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
in order to export private message data.

{start_tabs}

1. Make sure that you are an owner or admin of your Slack
   workspace. If you are one, the Slack web application will display
   that in your profile, in a banner covering the bottom of your
   avatar.

2. [Export your Slack message history](https://my.slack.com/services/export).
   You should be able to download a `zip` file with your data a few minutes
   after you start the export process.

3. You will also need to export your workspace's user data and custom emoji.
   To do so, start
   by [creating a new Slack app](https://api.slack.com/apps). Choose the "From
   scratch" creation option.

4. [Create a
   bot user](https://slack.com/help/articles/115005265703-Create-a-bot-for-your-workspace),
   following the instructions to add the following OAuth scopes to your bot:
    - `emoji:read`
    - `users:read`
    - `users:read.email`
    - `team:read`

5. [Install your new app](https://api.slack.com/authentication/basics#installing)
   to your Slack workspace.

6. You will immediately see a **Bot User OAuth Token**, which is a long
   string of numbers and characters starting with `xoxb-`. Copy this token. You
   will use it to download user and emoji data from your Slack workspace.

{end_tabs}

### Import your data into Zulip

To start using Zulip, you will need to choose between Zulip Cloud and
self-hosting Zulip. For a simple managed solution, with no setup or maintenance
overhead, you can [sign up](/new/) for Zulip Cloud with just a few clicks.
Alternatively, you can [self-host](/self-hosting/) your Zulip organization. See
[here](/help/zulip-cloud-or-self-hosting) to learn more.

!!! warn ""

    **You can only import a Slack workspace as a new Zulip organization.** Slack
    workspace history cannot be added into an existing Zulip organization.

{start_tabs}

{tab|zulip-cloud}

#### Import into a Zulip Cloud organization

If you plan to use Zulip Cloud, we'll take it from here! Please e-mail
[support@zulip.com](mailto:support@zulip.com) with the following information:

1. The subdomain you would like to use for your organization. Your Zulip chat will
   be hosted at `<subdomain>.zulipchat.com`.

2. The `zip` file containing your Slack message history export.

3. Your Slack **Bot User OAuth Token**, which will be a long
   string of numbers and characters starting with `xoxb-`

!!! warn ""

    If the organization already exists, the import process will overwrite all data
    that's already there. If needed, we're happy to preserve your data by moving an
    organization you've already created to a new subdomain prior to running the import process.

{tab|self-hosting}

#### Import into a self-hosted Zulip server

Zulip's Slack import tool is robust, and has been used to import Slack
workspaces with 10,000 members and millions of messages. If you're planning on
doing an import much larger than that, or run into performance issues when
importing, [contact us](/help/contact-support) for help.

1. Follow steps
   [1](https://zulip.readthedocs.io/en/stable/production/install.html#step-1-download-the-latest-release)
   and
   [2](https://zulip.readthedocs.io/en/stable/production/install.html#step-2-install-zulip)
   of the guide for [installing a new Zulip
   server](https://zulip.readthedocs.io/en/stable/production/install.html).

1. Copy the `zip` file containing your Slack message history export onto your Zulip
server, and put it in `/tmp/`.

1. Log in to a shell on your Zulip server as the `zulip` user.

1. To import into an organization hosted on the root domain
(`EXTERNAL_HOST`) of the Zulip installation, run the following commands, replacing
`<token>` with your Slack **Bot User OAuth Token**.

    !!! tip ""
        The import could take several minutes to run, depending on how much data you're importing.

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

    !!! tip ""
        The server stop/restart commands are only necessary when
        importing on a server with minimal RAM, where an OOM kill might
        otherwise occur.

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
  visibility](/help/restrict-visibility-of-email-addresses),
  [message editing permissions](/help/configure-message-editing-and-deletion#configure-message-editing-and-deletion_1),
  and [how users can join your organization](/help/restrict-account-creation).

- Slack does not export user settings, so users in your organization may want to
  [customize their account settings](/help/getting-started-with-zulip).

- Slack's user roles are mapped to Zulip's [user
  roles](/help/roles-and-permissions) in the following way:

| Slack role              | Zulip role    |
|-------------------------|---------------|
| Workspace Primary Owner | Owner         |
| Workspace Owner         | Owner         |
| Workspace Admin         | Administrator |
| Member                  | Member        |
| Single Channel Guest    | Guest         |
| Multi Channel Guest     | Guest         |
| Channel creator         | none          |

- Messages in threads are imported, but they are not explicitly marked as
  being in a thread.

- Message edit history and `@user joined #channel_name` messages are not imported.

## Clean up after the Slack export

Once your organization has been successfully imported in to Zulip, you should
delete [the Slack app](https://api.slack.com/apps) that you created in order to
[export your Slack data](#export-your-slack-data).  This will prevent the OAuth
token from being used to access your Slack workspace in the future.

## Get your organization started with Zulip

Once the import process is completed, you will need to:

{start_tabs}

1. [Configure the settings for your organization](/help/customize-organization-settings),
   which are not exported from Slack. This includes settings like [email
   visibility](/help/restrict-visibility-of-email-addresses), [message editing
   permissions](/help/configure-message-editing-and-deletion#configure-message-editing-and-deletion_1),
   and [how users can join your organization](/help/restrict-account-creation).

2. All users from your Slack workspace will have accounts in your new Zulip
   organization. However, you will need to decide how users will log in for the first time (see below).

3. Share the URL for your new Zulip organization, and (recommended) the [Getting
   started with Zulip guide](/help/getting-started-with-zulip).

4. Migrate any [integrations](/integrations), which is easy to do with Zulip's
   [Slack-compatible incoming webhook](/integrations/doc/slack_incoming).

{end_tabs}


### Decide how users will log in

When user accounts are imported from Slack, users initially do not have passwords
configured. There are a few options for how users can log in for the first time.

!!! tip ""
    For security reasons, Slack passwords are never exported.

### Allow users to log in with non-password authentication

When you create your organization, users will immediately be able to log in with
[authentication methods](/help/configure-authentication-methods) that do not
require a password. Zulip offers a variety of authentication methods, including
Google, GitHub, GitLab, Apple, LDAP and [SAML](/help/saml-authentication).

### Send password reset emails to all users

You can send password reset emails to all users in your organization, which
will allow them to set an initial password.

If you imported your organization into Zulip Cloud, simply e-mail
[support@zulip.com](mailto:support@zulip.com) to request this.

#### Send password reset emails (self-hosted organization)

{start_tabs}

{tab|default-subdomain}

1. To test the process, start by sending yourself a password reset email by
   using the following command:

     ```
     ./manage.py send_password_reset_email -u username@example.com
     ```

1. When ready, send password reset emails to all users by
   using the following command:

     ```
     ./manage.py send_password_reset_email -r '' --all-users
     ```

{tab|custom-subdomain}

1. To test the process, start by sending yourself a password reset email by
   using the following command:

     ```
     ./manage.py send_password_reset_email -u username@example.com
     ```

1. When ready, send password reset emails to all users by
   using the following command:

     ```
     ./manage.py send_password_reset_email -r <subdomain> --all-users
     ```

{end_tabs}

### Manual password resets

Alternatively, users can reset their own passwords by following the instructions
on your organization's login page.

## Related articles

* [Choosing between Zulip Cloud and self-hosting](/help/zulip-cloud-or-self-hosting)
* [Setting up your organization](/help/getting-your-organization-started-with-zulip)
* [Slack-compatible incoming webhook](/integrations/doc/slack_incoming)
* [Getting started with Zulip](/help/getting-started-with-zulip)
