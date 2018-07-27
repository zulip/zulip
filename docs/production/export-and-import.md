# Export and import

Zulip has high quality export and import tools that can be used to move data
from one Zulip server to another, do backups or compliance work, or migrate
from your own servers to the hosted Zulip Cloud service.

When using these tools, it's important to ensure that the Zulip server
you're exporting from and the one you're exporting to are running the
same version of Zulip, since we do change and extend the format from
time to time.

## Export your Zulip data

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

## Import into a new Zulip server

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

**Warning:** This will destroy all existing data in your Zulip server

## Import into an existing Zulip server

If you already have some organizations hosted on your Zulip server, and
want to import an additional Zulip organization, you can use the
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

## Logging in

Once the import completes, all your users will have accounts in your
new Zulip organization, but those accounts won't have passwords yet
(since for security reasons, passwords are not exported).
Your users will need to either authenticate using something like
Google auth, or start by resetting their passwords.

You can use the `./manage.py send_password_reset_email` command to
send password reset emails to your users.  We
recommend starting with sending one to yourself for testing:

```
./manage.py send_password_reset_email -u username@example.com
```

and then once you're ready, you can email them to everyone using e.g.
```
./manage.py send_password_reset_email -r '' --all-users
```

(replace `''` with your subdomain if you're using one).
