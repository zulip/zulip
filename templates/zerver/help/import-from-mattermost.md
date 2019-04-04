# Import from Mattermost

Starting with Zulip 2.1, Zulip supports importing data from Mattermost,
including users, channels, messages, and custom emoji.


**Note:** You can only import a Mattermost team as a new Zulip
organization. In particular, you cannot use this tool to import data
into an existing Zulip organization.

## Import from Mattermost

First, export your data.

1. SSH into your Mattermost app server

2. Run the following command to export the data.
  `docker exec -it mattermost-docker_app_1 mattermost export bulk export.json --all-teams`

3. This will generate `export.json` and `exported_emoji` directory inside
  **mattermost-docker_app_1** container. `exported_emoji` folder would be only
  created if your Mattermost server has custom emojis.

4. SSH into to **mattermost-docker_app_1** container by running the following command.
  `exec -it mattermost-docker_app_1 sh`

4. Tar the exported files by running the following command.
  `tar -cf export.tar exported_emoji/ export.json`

5. Now download the export.tar file from the Docker container to your local computer.

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

Extract the `export.tar` to any directory of your choice.

```bash
mkdir <exported_directory>
tar -xvf export.tar -C <exported_directory>
```

To import with the most common configuration, run the following commands
replacing `<team-name>` with the name of the team you want to import from
Mattermost export.

```
cd /home/zulip/deployments/current
./manage.py convert_mattermost_data <exported_directory> --output converted_mattermost_data
./manage.py import "" converted_mattermost_data/<team-name>
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
./manage.py import <subdomain> converted_mattermost_data/<team-name>
```

{!import-login.md!}

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/maintain-secure-upgrade.html#upgrading-from-a-git-repository

## Limitations

Mattermost currently does not support exporting private messages and group messages
between users, user avatars, uploaded files and message attachments. We would
be adding support for exporting them as well as Mattermost supports it.

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/maintain-secure-upgrade.html#upgrading-from-a-git-repository
