# Import from self-hosted Zulip

This guide explains the process of migrating your Zulip organization from a self-hosted instance to Zulip Cloud. The migration involves exporting data from your self-hosted instance and importing it into Zulip Cloud.

## Pre-Migration Steps

Before you begin the migration process, make sure you have the following:

1. **Upgrade Your Zulip Server (For Zulip Cloud Imports)**

    If you intend to import data into Zulip Cloud, ensure that your self-hosted Zulip server is [upgraded](https://zulip.readthedocs.io/en/latest/production/upgrade.html) to the zulip-cloud-current branch. Use the following command:

        /home/zulip/deployments/current/scripts/upgrade-zulip-from-git zulip-cloud-current

2. **Prevent Changes During Export**

    For optimal results, it's recommended to prevent changes to your Zulip organization during the export process. You can achieve this by either stopping the server entirely or deactivating the organization temporarily. Choose one of the following options:

    - Option 1: Stop the Server

        ```
        ./scripts/stop-server
        ```



    - Option 2: Deactivate the Organization

        ```
        ./manage.py export --deactivate
        ```

## Import process overview
To import your self hosted Zulip organization into Zulip Cloud, you will need to take the
following steps, which are described in more detail below:

{start_tabs}

1. [Export your self hosted Zulip data](#export-your-self-hosted-zulip-data).

2. [Import your Mattermost data into Zulip](#import-your-data-in-zulip-cloud).

3. [Get your organization started with Zulip](#get-your-organization-started-with-zulip)!

4. [Decide how users will log in](#decide-how-users-will-log-in)
{end_tabs}

## Import your self hosted Zulip into Zulip Cloud

### Export your self hosted Zulip data

Zulip’s powerful [data export tool](https://zulip.readthedocs.io/en/latest/production/export-and-import.html#data-export) is designed to handle migration of a Zulip organization between different Zulip installations; as a result, these exports contain all non-transient data for a Zulip organization, with the exception of secrets, like passwords and API keys.

We recommend using the [backup tool](https://zulip.readthedocs.io/en/latest/production/export-and-import.html#backups) in all scenarios where it is applicable, because this data export process has a few downsides in comparison:

- All users will have their passwords randomized and be logged out of their accounts, both on web and mobile clients.

- All bots and integrations will need to be updated with new API keys.

- Users, streams, and messages are usually renumbered, which will break most links from external programs referencing these objects.



{start_tabs}

{tab|backup}

1. The Zulip server has a built-in [backup tool](https://zulip.readthedocs.io/en/latest/production/export-and-import.html#backups) which can be used to export your data:

        # As the zulip user
        /home/zulip/deployments/current/manage.py backup
        # Or as root
        su zulip -c '/home/zulip/deployments/current/manage.py backup'

1. The backup tool provides the following options:
    - `--output=/tmp/backup.tar.gz`: Filename to write the backup tarball to (default: write to a file in `/tmp`). On success, the console output will show the path to the output tarball.

    - `--skip-db`: Skip backup of the database. Useful if you’re using a remote PostgreSQL host with its own backup system and just need to back up non-database state.

    - `--skip-uploads`: If LOCAL_UPLOADS_DIR is set, user-uploaded files in that directory will be ignored.

This will generate a `.tar.gz` archive containing all the data stored on your Zulip server that would be needed to restore your Zulip server’s state on another machine perfectly.



{tab|export}

Follow these steps to export your data using Zulip's Data Export Tool:

1. Log in to a shell on your Zulip server as the `zulip` user. Run the following commands:

        cd /home/zulip/deployments/current
        # ./scripts/stop-server
        # export DEACTIVATE_FLAG="--deactivate"   # Deactivates the organization
        ./manage.py export -r '' $DEACTIVATE_FLAG # Exports the data


    (The -r option lets you specify the organization to export; '' is the default organization hosted at the Zulip server’s root domain.)

2. This will generate a compressed archive with a name like `/tmp/zulip-export-zcmpxfm6.tar.gz`. The archive contains several JSON files (containing the Zulip organization’s data) as well as an archive of all the organization’s uploaded files.

{end_tabs}

### Import your data in Zulip Cloud

{!import-into-a-zulip-cloud-organization.md!}

{!import-zulip-cloud-organization-warning.md!}



## Get your organization started with Zulip

{!import-get-your-organization-started.md!}

## Decide how users will log in

When user accounts are imported, users initially do not have passwords
configured. There are a few options for how users can log in for the first time.

!!! tip ""

    For security reasons, passwords are never exported.

### Allow users to log in with non-password authentication

When you create your organization, users will immediately be able to log in with
[authentication methods](/help/configure-authentication-methods) that do not
require a password. Zulip offers a variety of authentication methods, including
Google, GitHub, GitLab, Apple, LDAP and [SAML](/help/saml-authentication).

### Send password reset emails to all users

You can send password reset emails to all users in your organization, which
will allow them to set an initial password. E-mail
[support@zulip.com](mailto:support@zulip.com) to request this.

!!! warn ""

    To avoid confusion, first make sure that the users in your
    organization are aware that their account has been moved to
    Zulip, and are expecting to receive a password reset email.

### Manual password resets

Alternatively, users can reset their own passwords by following the instructions
on your Zulip organization's login page.

## Related Articles
* [Joining a Zulip organization](/help/join-a-zulip-organization)
* [Setting up your organization](/help/getting-your-organization-started-with-zulip)
* [Getting started with Zulip](/help/getting-started-with-zulip)
