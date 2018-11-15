# Import from Gitter (beta)

Zulip supports importing data from Gitter, including users, channels,
messages, attachments, and avatars.

**Note:** You can only import a Gitter room as a new Zulip organization. In
particular, this tool you cannot use this tool to import from Gitter into an
existing Zulip organization.

## Import from Gitter

First, export your data from Gitter.

1. [Export your Gitter data](https://github.com/minrk/archive-gitter). You will
   receive json files of the public rooms that you are a part of.
   Select the `gitter_data.json` file of the room which you want to import into
   Zulip.

    !!! warn ""
        **Note:** You'll need a gitter API token to export data. You can get this
        token by following the instructions in the "**Getting Started**" section of the
        [gitter documentation](https://developer.gitter.im/docs/).

### Import into zulipchat.com

Email support@zulipchat.com with `gitter_data.zip` and your desired
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

Log in to a shell on your Zulip server as the `zulip` user. To import with
the most common configuration, run the following commands, replacing
`<token>` with the value generated above.

```
cd /home/zulip/deployments/current
./manage.py convert_gitter_data gitter_data.json --output converted_gitter_data
./manage.py import '' converted_gitter_data
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
./manage.py import <subdomain> converted_gitter_data
```

{!import-login.md!}

## Create organization administrators

The [Gitter API][gitter-api-user-data] don't contain data on which
users are administrators of the Gitter channel.  As a result, all
Gitter users are imported into Zulip as normal users.  You can follow
the Zulip documentation on
[making a user an administrator from the terminal][grant-admin-access]
to mark the appropriate users as administrators.

[grant-admin-access]: https://zulip.readthedocs.io/en/latest/production/maintain-secure-upgrade.html#grant-administrator-access)
[gitter-api-user-data]: https://developer.gitter.im/docs/user-resource

## Caveats

- The [Gitter data export tool](https://github.com/minrk/archive-gitter)
  doesn't support exporting private gitter channels.

- This tool doesn't yet support merging importing Gitter channels into
  a single Zulip organization.

- This tool doesn't translate Gitter's markdown format into Zulip
  format markdown (there are a few corner cases where the syntax is
  different).  Additionally, Gitter's
  [issue mentions](https://gitter.zendesk.com/hc/en-us/articles/200176692-Issue-and-Pull-Request-mentions)
  aren't translated into anything yet.

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/maintain-secure-upgrade.html#upgrading-from-a-git-repository
