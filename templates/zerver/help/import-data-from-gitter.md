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
   Select the file, `gitter_data.json`, of the room which you want to import to the
   Zulip server.

    !!! warn ""
        **Note:** You need the gitter API token to export data. You can get the
        this token by following the instructions mentioned in the
        [gitter documentation](https://developer.gitter.im/docs/).

### Import into a new Zulip server

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

- [Gitter data export](https://github.com/minrk/archive-gitter) doesn't support
  the export of the private gitter rooms.

- Gitter markdown and issue mentions hasn't been mapped yet.
