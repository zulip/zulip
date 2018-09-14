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

### Import into a new Zulip server

Because the Gitter import tool is very new, we recommend first
upgrading your new Zulip server to the latest `master` branch,
using [upgrade-zulip-from-git][upgrade-zulip-from-git] to avoid
bugs in the earliest versions of the Gitter import tool.

Log in to a shell on your Zulip server as the `zulip` user. Run the
following commands.

```
./manage.py convert_gitter_data gitter_data.json --output converted_gitter_data
./manage.py import --destroy-rebuild-database '' converted_gitter_data
```

!!! warn ""
    **Warning:** This will destroy all existing data in your Zulip server

### Import into an existing Zulip server

If you already have some organizations hosted on your Zulip server,
and want to add import your Gitter data as a new Zulip organization,
you can use the following procedure.

Log in to your Zulip server as the `zulip` user. Run the following
commands, replacing `<subdomain>` with the subdomain of the URL
you'd like for your imported Zulip organization.

```
./manage.py convert_gitter_data gitter_data.json --output converted_gitter_data
./manage.py import --destroy-rebuild-database <subdomain> converted_gitter_data
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
