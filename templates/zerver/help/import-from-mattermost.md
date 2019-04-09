# Import from Mattermost

Starting with Zulip 2.1, Zulip supports importing data from Mattermost,
including users, channels, messages, and custom emoji.


**Note:** You can only import a Mattermost team as a new Zulip
organization. In particular, you cannot use this tool to import data
into an existing Zulip organization.

## Import from Mattermost

First, export your data.  The following instructions assume you're
running Mattermost inside a Docker container. Replace `<username>` and
`<server_ip>` with appropriate values accordingly.

1. SSH into your Mattermost server running the docker containers.

    ```
    ssh <username>@><server_ip>
    ```

2. Navigate to the the Mattermost docker directory. On most installs the
   directory should be `mattermost-docker`.

    ```
    cd mattermost-docker/
    ```

3. Run the following commands to export the data from all teams on your server as a tar file.

    ```
    docker exec -it mattermost-docker_app_1 mattermost \
        export bulk data/export.json --all-teams
    cd volumes/app/mattermost/data/
    mkdir -p exported_emoji
    tar --transform 's|^|mattermost/|' -czf export.tar.gz \
        exported_emoji/ export.json
    ```

4. Now exit out of the Mattermost server.

    `exit`

5. Finally copy the exported tar file from the server to your local computer. Make sure to replace
   `mattermost-docker` with the correct directory if it is different in your case.

    ```
    scp <username>@<server_ip>:mattermost-docker/volumes/app/mattermost/data/export.tar.gz .
    ```
  
### Import into zulipchat.com

Email support@zulipchat.com with your exported archive and your desired Zulip
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

Log in to a shell on your Zulip server as the `zulip` user.

Extract the `export.tar.gz` to `/home/zulip/mattermost` as follows.

```bash
cd /home/zulip
tar -xzvf export.tar.gz
```

To import with the most common configuration, run the following commands
replacing `<team-name>` with the name of the team you want to import from
Mattermost export.

```
cd /home/zulip/deployments/current
./manage.py convert_mattermost_data /home/zulip/mattermost --output /home/zulip/converted_mattermost_data
./manage.py import "" /home/zulip/converted_mattermost_data/<team-name>
```

This could take several minutes to run, depending on how much data you're
importing.

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

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/maintain-secure-upgrade.html#upgrading-from-a-git-repository

## Limitations

Mattermost's export tool is incomplete and does not support exporting
the following data:

* private messages and group private messages between users
* user avatars
* uploaded files and message attachments.

We expect to add support for importing these data from Mattermost once
Mattermost's export tool includes them.

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/maintain-secure-upgrade.html#upgrading-from-a-git-repository
