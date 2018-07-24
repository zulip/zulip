# Import data from Gitter (beta)

Zulip supports importing data from Gitter, including users, channels,
messages, attachments, and avatars.

!!! warn ""
    These instructions require shell access to the Zulip server. If you'd like
    to import a Gitter organization into the hosted zulipchat.com service,
    contact support@zulipchat.com.

First, you need to do some things in Gitter to setup the export:

1. [Export your Gitter data](https://github.com/minrk/archive-gitter). You will
   receive json files of the public rooms that you are a part of.
   Select the `gitter_data.json` file of the room which you want to import into
   Zulip.

    !!! warn ""
        **Note:** You'll need a gitter API token to export data. You can get
        this token by following the instructions in the
        [gitter documentation](https://developer.gitter.im/docs/).

### Import into a new Zulip server

!!! warn ""
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

## Caveats

- The [Gitter data export](https://github.com/minrk/archive-gitter)
  that powers this doesn't support exporting private gitter rooms.

- This tool doesn't do any translation of the Gitter markdown into
  Zulip format markdown; additionally, Gitter's "issue mentions"
  aren't translated into anything yet.

[upgrade-zulip-from-git]: https://zulip.readthedocs.io/en/latest/production/maintain-secure-upgrade.html#upgrading-from-a-git-repository
