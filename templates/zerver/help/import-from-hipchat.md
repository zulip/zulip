# Import from HipChat/Stride

Starting with Zulip 1.9, Zulip supports importing data from HipChat and Stride,
including users, rooms, messages, avatars, and custom emoji.

This tool has been used to import HipChat teams with thousands of
members, thousands of streams and millions of messages. If you're
planning on doing an import much larger than that, or run into
performance issues when importing, email us at support@zulipchat.com
for help.

**Note:** You can only import a HipChat or Stride group as a new Zulip
organization. In particular, you cannot use this tool to import data
into an existing Zulip organization.

## Import from HipChat or Stride

First, export your data.

{start_tabs}
{tab|cloud}

1. Log in at `yourdomain.hipchat.com/admin/`.

1. Click on the **Data Export** tab.

1. Select the data to export.

1. Set a **Password** to encrypt your export.

1. Click **Export**.

Once the export has completed, the export will be available to you in the
admin console.

{tab|server}

1. Upgrade to the latest version to ensure you have the latest updates to
   the HipChat export dashboard.

1. Log in at the domain name configured for your Hipchat Server.

1. Click on **Server Admin > Export**.

1. Select the data to export.

1. Set a **Password** to encrypt your export.

1. Click **Export**.

Once the export has completed, you will receive an **email** with a link to
download the file.

!!! tip ""
    If you are not on the latest version of Hipchat Server / Data Center,
    you can do a command line export with `hipchat export --export`.  See
    HipChat's [command line export docs][cli-export] for more information.

{tab|stride}

1. Log in at `yourdomain.atlassian.net/admin/`.

1. Click on **Stride** in the bottom left in Application Settings.

1. Click **Create export**.

1. Select the data to export.

1. Set a **Password** to encrypt your export.

1. Click **Export**.

{end_tabs}

!!! warn ""
    **Note:** Only HipChat Group Administrators can export data from HipChat.

[cli-export]: https://confluence.atlassian.com/hipchatdc3/export-data-from-hipchat-data-center-913476832.html

### Import into zulipchat.com

Email support@zulipchat.com with your exported archive and your desired Zulip
subdomain. Your imported organization will be hosted at
`<subdomain>.zulipchat.com`.

Also, see the [caveats section notes on room subscribers](#caveats)
and consider whether you want to also send a HipChat API key to
provide a more faithful import.

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
`<exported_file>` with the HipChat export file and `<password>` with the
password you set during the HipChat export.

```
cd /home/zulip/deployments/current
openssl aes-256-cbc -d -in <exported_file> -out hipchat.tar.gz -md md5 -pass pass:<password>
./manage.py convert_hipchat_data hipchat.tar.gz --output converted_hipchat_data
./manage.py import '' converted_hipchat_data
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
./manage.py import <subdomain> converted_hipchat_data
```

{!import-login.md!}

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/maintain-secure-upgrade.html#upgrading-from-a-git-repository

## Caveats

- While the import tool will correctly import the subscribers of
private rooms precisely, HipChat does not store the subscribers of
public rooms when those users don't have an active client.  As a
result, HipChat's data exports don't include subscribers for public
rooms.  You can pick one of the following options for handling this:
    1. Subscribe all users to all public streams (the default, which is
    good for small organizations),
    2. Subscribe only HipChat room owners to public streams (and plan
    for users to subscribe to the imported Zulip streams manually
    after the import completes) using the `--slim-mode` option to `manage.py
    convert_hipchat_data`, or
    3. Use the [HipChat API][hipchat-api-tokens] to fetch each room's
    current room subscribers as of the moment the import is run.
    Because HipChat doesn't store subscribers to a room when clients
    are not connected, these subscriptons will be incomplete for users
    who don't have an actively connected client at the time of the
    import.  You need to pass the token via `--token=abcd1234` in
    `manage.py convert_hipchat_data` (or include it in your request,
    if importing into Zulip Cloud).

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/maintain-secure-upgrade.html#upgrading-from-a-git-repository
[hipchat-api-tokens]: https://developer.atlassian.com/server/hipchat/hipchat-rest-api-access-tokens/
