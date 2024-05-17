# Import from Mattermost

{!import-workspace-to-zulip.md!}

## Import process overview

To import your Mattermost organization into Zulip, you will need to take the
following steps, which are described in more detail below:

{start_tabs}

1. [Export your Mattermost data](#export-your-mattermost-data).

1. [Import your Mattermost data into Zulip](#import-your-data-into-zulip).

1. [Get your organization started with Zulip](#get-your-organization-started-with-zulip)!

{end_tabs}

## Import your organization from Mattermost into Zulip

### Export your Mattermost data

Mattermost's [bulk export tool](https://docs.mattermost.com/manage/bulk-export-tool.html)
allows you to export all public and private channel messages.

The instructions below correspond to various common ways Mattermost is installed; if
yours isn't covered, [contact us](/help/contact-support) and we'll help you out.

Replace `<username>` and `<server_ip>` with the appropriate values below.

{start_tabs}

{tab|mm-default}

1. SSH into your Mattermost production server.

    ```
    ssh <username>@<server_ip>
    ```

1. Navigate to the directory which contains the Mattermost executable.
   On a default install of Mattermost, the directory is `/opt/mattermost/bin`.

    ```
    cd /opt/mattermost/bin
    ```

1. Create an export of all your Mattermost teams, as a tar file.

    ```
    sudo ./mattermost export bulk export.json --all-teams --attachments
    mkdir -p exported_emoji
    tar --transform 's|^|mattermost/|' -czf export.tar.gz \
        data/ exported_emoji/ export.json
    ```

1. Exit your shell on the Mattermost server.

    `exit`

1. Finally, copy the exported tar file from the server to your local
   computer.  You may need to replace `/opt/mattermost/bin/` with the
   path to your Mattermost installation.

    ```
    scp <username>@<server_ip>:/opt/mattermost/bin/export.tar.gz .
    ```

{tab|mm-cloud}

1. Make sure you have [mmctl](https://github.com/mattermost/mmctl) installed - these
   instructions assume your version is `7.5.1` or higher.

1. Log into your Mattermost Cloud instance using your administrator credentials.

    ```
    mmctl auth login https://yourdomain.cloud.mattermost.com
    ```

1. Create a full export of the server, including attached files.

    ```
    mmctl export create
    ```

1. List all of the exports on the server, and copy the name of the
   latest one to your clipboard.

    ```
    mmctl export list
    ```

1. Download the export to your local computer, replacing
   `latest_export` with the actual file name from the previous step.

    ```
    mmctl export download latest_export.zip
    ```

{tab|mm-docker}

1. SSH into the server hosting your Mattermost docker container.

    ```
    ssh <username>@<server_ip>
    ```

1. Navigate to the Mattermost docker directory. On most installs, the
   directory should be `mattermost-docker`.

    ```
    cd mattermost-docker/
    ```

1. Create an export of all your Mattermost teams, as a tar file.

    ```
    docker exec -it mattermost-docker_app_1 mattermost \
        export bulk data/export.json --all-teams --attachments
    cd volumes/app/mattermost/data/
    mkdir -p exported_emoji
    tar --transform 's|^|mattermost/|' -czf export.tar.gz \
        data/ exported_emoji/ export.json
    ```

1. Exit your shell on the Mattermost server.

    `exit`

1. Finally, copy the exported tar file from the server to your local
   computer. You may need to replace `mattermost-docker` with the
   appropriate path for your installation.

    ```
    scp <username>@<server_ip>:mattermost-docker/volumes/app/mattermost/data/export.tar.gz .
    ```

{tab|mm-gitlab-omnibus}

1. SSH into your GitLab Omnibus server.

1. Create an export of all your Mattermost teams, as a tar file.

    ```
    cd /opt/gitlab/embedded/service/mattermost
    sudo -u \
        mattermost /opt/gitlab/embedded/bin/mattermost \
        --config=/var/opt/gitlab/mattermost/config.json \
        export bulk export.json --all-teams --attachments
    mkdir -p exported_emoji
    tar --transform 's|^|mattermost/|' -czf export.tar.gz \
        data/ exported_emoji/ export.json
    ```

1. Exit your shell on the GitLab Omnibus server.

    `exit`

1. Finally, copy the exported tar file from GitLab Omnibus to your local computer.

    ```
    scp <username>@<server_ip>:/opt/gitlab/embedded/bin/mattermost/export.tar.gz .
    ```
{end_tabs}

### Import your data into Zulip

{!import-your-data-into-zulip.md!}

{start_tabs}

{tab|zulip-cloud}

{!import-into-a-zulip-cloud-organization.md!}

{!import-zulip-cloud-organization-warning.md!}

{tab|self-hosting}

{!import-into-a-self-hosted-zulip-server.md!}

1. To import into an organization hosted on the root domain
   (`EXTERNAL_HOST`) of the Zulip installation, run the following commands,
   replacing `<team-name>` with the name of the Mattermost team you want to import.

    {!import-self-hosted-server-tips.md!}

    ```
    cd /home/zulip/deployments/current
    ./scripts/stop-server
    ./manage.py convert_mattermost_data /tmp/mattermost_data.tar.gz --output /tmp/converted_mattermost_data
    ./manage.py import '' /tmp/converted_mattermost_data/<team-name>
    ./scripts/start-server
    ```

    Alternatively, to import into a custom subdomain, run:

    ```
    cd /home/zulip/deployments/current
    ./scripts/stop-server
    ./manage.py convert_mattermost_data /tmp/mattermost_data.tar.gz --output /tmp/converted_mattermost_data
    ./manage.py import <subdomain> /tmp/converted_mattermost_data/<team-name>
    ./scripts/start-server
    ```

1. Follow [step 4](https://zulip.readthedocs.io/en/stable/production/install.html#step-4-configure-and-use)
   of the guide for [installing a new Zulip
   server](https://zulip.readthedocs.io/en/stable/production/install.html).

{tab|mm-self-hosting-cloud-export}

{!import-into-a-self-hosted-zulip-server.md!}

1. To import into an organization hosted on the root domain
   (`EXTERNAL_HOST`) of the Zulip installation, run the following commands,
   replacing `<team-name>` with the name of the Mattermost team you want to import.

    {!import-self-hosted-server-tips.md!}

    ```
    unzip latest_export.zip -d /tmp/my_mattermost_export
    mv /tmp/my_mattermost_export/import.jsonl /tmp/my_mattermost_export/export.json
    cd /home/zulip/deployments/current
    ./scripts/stop-server
    ./manage.py convert_mattermost_data /tmp/my_mattermost_export --output /tmp/converted_mattermost_data
    ./manage.py import '' /tmp/converted_mattermost_data/<team-name>
    ./scripts/start-server
    ```

    Alternatively, to import into a custom subdomain, run:

    ```
    unzip latest_export.zip -d /tmp/my_mattermost_export
    mv /tmp/my_mattermost_export/import.jsonl /tmp/my_mattermost_export/export.json
    cd /home/zulip/deployments/current
    ./scripts/stop-server
    ./manage.py convert_mattermost_data /tmp/my_mattermost_export --output /tmp/converted_mattermost_data
    ./manage.py import <subdomain> /tmp/converted_mattermost_data/<team-name>
    ./scripts/start-server
    ```

1. Follow [step 4](https://zulip.readthedocs.io/en/stable/production/install.html#step-4-configure-and-use)
   of the guide for [installing a new Zulip
   server](https://zulip.readthedocs.io/en/stable/production/install.html).

{end_tabs}

#### Import details

Whether you are using Zulip Cloud or self-hosting Zulip, here are a few notes to
keep in mind about the import process:

- Mattermost does not export workspace settings, so you will need to [configure
  the settings for your Zulip organization](/help/customize-organization-settings).
  This includes settings like [email
  visibility](/help/configure-email-visibility),
  [message editing permissions](/help/restrict-message-editing-and-deletion),
  and [how users can join your organization](/help/restrict-account-creation).

- Mattermost's user roles are mapped to Zulip's [user
  roles](/help/roles-and-permissions) in the following way:

| Mattermost role         | Zulip role    |
|-------------------------|---------------|
| Team administrator      | Owner         |
| Member                  | Member        |

- Mattermost's export tool does not support exporting user avatars or message
  edit history.

- Direct messages will only be imported from Mattermost workspaces containing
  a single team. This is because Mattermost's data exports do not associate
  direct messages with a specific Mattermost team.

- Messages in threads are imported, but they are not explicitly marked as
  being in a thread.

## Get your organization started with Zulip

{!import-get-your-organization-started.md!}

## Decide how users will log in

{!import-how-users-will-log-in.md!}

## Related articles

* [Choosing between Zulip Cloud and self-hosting](/help/zulip-cloud-or-self-hosting)
* [Setting up your organization](/help/getting-your-organization-started-with-zulip)
* [Getting started with Zulip](/help/getting-started-with-zulip)
