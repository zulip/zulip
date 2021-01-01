# Import from Mattermost

Starting with Zulip 2.1, Zulip supports importing data from Mattermost,
including users, channels, messages, and custom emoji.


**Note:** You can only import a Mattermost team as a new Zulip
organization. In particular, you cannot use this tool to import data
into an existing Zulip organization.

## Import from Mattermost

First, export your data from Mattermost.
The instructions below correspond to various common ways Mattermost is installed; if
yours isn't covered, [contact us](/help/contact-support) and we'll help you out.

Replace `<username>` and `<server_ip>` with the appropriate values below.

{start_tabs}

{tab|mm-default}

1. SSH into your Mattermost production server.

    ```
    ssh <username>@<server_ip>
    ```

2. Navigate to the directory which contains the Mattermost executable.
   On a default install of Mattermost, the directory is `/opt/mattermost/bin`.

    ```
    cd /opt/mattermost/bin
    ```

3. Create an export of all your Mattermost teams, as a tar file.

    ```
    sudo ./mattermost export bulk export.json --all-teams
    mkdir -p exported_emoji
    tar --transform 's|^|mattermost/|' -czf export.tar.gz \
        exported_emoji/ export.json
    ```

4. Exit your shell on the Mattermost server.

    `exit`

5. Finally, copy the exported tar file from the server to your local
   computer.  You may need to replace `/opt/mattermost/bin/` with the
   path to your Mattermost installation.

    ```
    scp <username>@<server_ip>:/opt/mattermost/bin/export.tar.gz .
    ```

{tab|mm-docker}

1. SSH into the server hosting your Mattermost docker container.

    ```
    ssh <username>@<server_ip>
    ```

2. Navigate to the the Mattermost docker directory. On most installs the
   directory should be `mattermost-docker`.

    ```
    cd mattermost-docker/
    ```

3. Create an export of all your Mattermost teams, as a tar file.

    ```
    docker exec -it mattermost-docker_app_1 mattermost \
        export bulk data/export.json --all-teams
    cd volumes/app/mattermost/data/
    mkdir -p exported_emoji
    tar --transform 's|^|mattermost/|' -czf export.tar.gz \
        exported_emoji/ export.json
    ```

4. Exit your shell on the Mattermost server.

    `exit`

5. Finally, copy the exported tar file from the server to your local
   computer. You may need to replace `mattermost-docker` with the
   appropriate path for your installation.

    ```
    scp <username>@<server_ip>:mattermost-docker/volumes/app/mattermost/data/export.tar.gz .
    ```

{tab|mm-gitlab-omnibus}

1. SSH into your GitLab Omnibus server.

2. Create an export of all your Mattermost teams, as a tar file.

    ```
    cd /opt/gitlab/embedded/service/mattermost
    sudo -u \
        mattermost /opt/gitlab/embedded/bin/mattermost \
        --config=/var/opt/gitlab/mattermost/config.json \
        export bulk export.json --all-teams
    mkdir -p exported_emoji
    tar --transform 's|^|mattermost/|' -czf export.tar.gz \
        exported_emoji/ export.json
    ```

3. Exit your shell on the GitLab Omnibus server.

    `exit`

4. Finally, copy the exported tar file from GitLab Omnibus to your local computer.

    ```
    scp <username>@<server_ip>:/opt/gitlab/embedded/bin/mattermost/export.tar.gz .
    ```
{end_tabs}

### Import into Zulip Cloud

Email support@zulip.com with your exported archive,
the name of the Mattermost team you want to import, and your desired Zulip
subdomain. Your imported organization will be hosted at
`<subdomain>.zulipchat.com`.

If you've already created a test organization at
`<subdomain>.zulipchat.com`, let us know, and we can rename the old
organization first.

### Import into a self-hosted Zulip server

First
[install a new Zulip server](https://zulip.readthedocs.io/en/stable/production/install.html),
skipping "Step 3: Create a Zulip organization, and log in" (you'll
create your Zulip organization via the data import tool instead).

Use [upgrade-zulip-from-git][upgrade-zulip-from-git] to
upgrade your Zulip server to the latest `master` branch.

Log in to a shell on your Zulip server as the `zulip` user. To import with
the most common configuration, run the following commands, replacing
`<team-name>` with the name of the Mattermost team you want to import.

```
cd /home/zulip
tar -xzvf export.tar.gz
cd /home/zulip/deployments/current
supervisorctl stop all  # Stop the Zulip server
./manage.py convert_mattermost_data /home/zulip/mattermost --output /home/zulip/converted_mattermost_data
./manage.py import "" /home/zulip/converted_mattermost_data/<team-name>
./scripts/restart-server
```

This could take several minutes to run, depending on how much data
you're importing.  The server stop/restart is only necessary when
importing on a server with minimal RAM, where an OOM kill might
otherwise occur.

**Import options**

The commands above create an imported organization on the root domain
(`EXTERNAL_HOST`) of the Zulip installation. You can also import into a
custom subdomain, e.g. if you already have an existing organization on the
root domain. Replace the last line above with the following, after replacing
`<subdomain>` with the desired subdomain.

```
./manage.py import <subdomain> /home/zulip/converted_mattermost_data/<team-name>
```

{!import-login.md!}

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/upgrade-or-modify.html#upgrading-from-a-git-repository

## Caveats

Mattermost's export tool is incomplete and does not support exporting
the following data:

* user avatars
* uploaded files and message attachments.

We expect to add support for importing these data from Mattermost once
Mattermost's export tool includes them.

Additionally, Mattermost's data exports do not associated private
messages with a specific Mattermost team.  For that reason, the import
tool will only import private messages for data export archives
containing a single Mattermost team.

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/upgrade-or-modify.html#upgrading-from-a-git-repository
