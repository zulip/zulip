# Import or export a Zulip organization

Zulip has high quality export and import tools that can be used to
migrate from the hosted Zulip Cloud service to or from your own
servers, move data from one Zulip server to another, do backups or
compliance work, etc.

The import half of these tools also powers our
[Slack import feature](/help/import-from-slack).

!!! warn ""
    These instructions currently require shell access to the Zulip
    server. If you'd like to migrate to or from the Zulip Cloud
    service hosted on zulipchat.com, contact support@zulipchat.com.

When using these tools, it's important to ensure that the Zulip server
you're exporting from and the one you're exporting to are running the
same version of Zulip (since we do change and extend the format from
time to time).

### Export your Zulip data

For best results, you'll want to shut down access to the organization
you are exporting with `manage.py deactivate_realm` before exporting,
so that nobody can send new messages (etc.) while you're exporting
data.  We include that in the instructions below.

Log in to a shell on your Zulip server as the `zulip` user. Run the
following commands:

```
cd /home/zulip/deployments/current
./manage deactivate_realm -r ''  # Deactivates the organization
./manage.py export -r ''  # Exports the data
```

(The `-r` option lets you specify the organization to export; `''` is
the default organization hosted at the Zulip server's root domain.)

This will generate a tarred archive with a name like
`/tmp/zulip-export-zcmpxfm6.tar.gz`.  The archive contains several
JSON files (containing the Zulip organization's data) as well as an
archive of all the organization's uploaded files.

### Import into a new Zulip server

Log in to a shell on your Zulip server as the `zulip` user. Run the
following commands, replacing the filename with the path to your data
export tarball:

```
cd /tmp
tar -xf /path/to/export/file/zulip-export-zcmpxfm6.tar.gz
cd /home/zulip/deployments/current
./manage.py import --destroy-rebuild-database '' /tmp/zulip-export-zcmpxfm6
./manage reactivate_realm -r ''  # Reactivates the organization
```

!!! warn ""
    **Warning:** This will destroy all existing data in your Zulip server

### Import into an existing Zulip server

If you already have some organizations hosted a your Zulip server, and
want to add import an additional Zulip organization, you can use the
following procedure.

Log in to your Zulip server as the `zulip` user. Run the following
commands, replacing the filename with the path to your data export
tarball, `<subdomain>` with the subdomain of the URL you'd like for
your imported Zulip organization.

```
cd /tmp
tar -xf /path/to/export/file/zulip-export-zcmpxfm6.tar.gz
cd /home/zulip/deployments/current
./manage.py import --import-into-nonempty <subdomain> /tmp/zulip-export-zcmpxfm6
./manage reactivate_realm -r ''  # Reactivates the organization
```

{!import-login.md!}
