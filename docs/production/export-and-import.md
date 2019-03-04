# Export and import

Zulip has high quality export and import tools that can be used to move data
from one Zulip server to another, do backups or compliance work, or migrate
from your own servers to the hosted Zulip Cloud service.

When using these tools, it's important to ensure that the Zulip server
you're exporting from and the one you're exporting to are running the
same version of Zulip, since we do change and extend the format from
time to time.

## Backups

If you want to move hardware for a self-hosted Zulip installation, we
recommend Zulip's
[database-level backup and restoration process][backups] for a better
experience.  Zulip's database-level backup process is faster,
structurally very unlikely to ever develop bugs, and will restore your
Zulip server to the exact state it was left in.  The big thing it
can't do is support a migration to a server hosting a different set of
organizations than the original one, e.g. migrations between
self-hosting and Zulip Cloud (because doing so in the general case
requires renumbering all the users/messages/etc.).

Zulip's export/import tools (documented on this page) have full
support for such a renumbering process.  While these tools are
carefully designed and tested to make various classes of bugs
impossible or unlikely, the extra complexity required for renumbering
makes them structurally more risky than the direct postgres backup
process.

[backups]: ../production/maintain-secure-upgrade.html#backups

## Preventing changes during the export

For best results, you'll want to shut down access to the organization
before exporting, so that nobody can send new messages (etc.)  while
you're exporting data.  There are two ways to do this:

1. `supervisorctl stop all`, which stops the whole server.  This is
preferred if you're not hosting multiple organizations, because it has
no side effects other than disabling the Zulip server for the
duration.
1. `manage.py deactivate_realm`, which deactivates the target
organization, logging out all active login sessions and preventing all
accounts in the from logging in or accessing the API.  This is
preferred for environments like Zulip Cloud where you might want to
export a single organization without disrupting any other users, and
the intent is to move hosting of the organization (and forcing users
to re-login would be required as part of the hosting migrateion
anyway).

We include both options in the instructions below, commented out so
that neither runs (using the `# ` at the start of the lines).  If
you'd like to use one of these options, remove the `# ` at the start
of the lines for the appropriate option.

## Export your Zulip data

Log in to a shell on your Zulip server as the `zulip` user. Run the
following commands:

```
cd /home/zulip/deployments/current
# ./manage.py deactivate_realm -r ''  # Deactivates the organization
# supervisorctl stop all # Stops the Zulip server
./manage.py export -r ''  # Exports the data
```

(The `-r` option lets you specify the organization to export; `''` is
the default organization hosted at the Zulip server's root domain.)

This will generate a tarred archive with a name like
`/tmp/zulip-export-zcmpxfm6.tar.gz`.  The archive contains several
JSON files (containing the Zulip organization's data) as well as an
archive of all the organization's uploaded files.

## Import into a new Zulip server

The Zulip server you're importing into needs to be running the same
version of Zulip as the server you exported from, so that the same
formats are consistent.  For exports from zulipchat.com, usually this
means you need to upgrade your Zulip server to the latest `master`
branch, using [upgrade-zulip-from-git][upgrade-zulip-from-git].

First [install a new Zulip server](../production/install.html),
skipping "Step 3: Create a Zulip organization, and log in" (you'll
create your Zulip organization via the data import tool instead).

If your new Zulip server is meant to fully replace a previous Zulip
server, you may want to copy the contents of `/etc/zulip` to your new
server at this point to reuse the server-level configuration and
secret keys from your old server.  See our
[documentation on backups][backups] for details on the contents of
this directory.

Log in to a shell on your Zulip server as the `zulip` user. Run the
following commands, replacing the filename with the path to your data
export tarball:

```
cd ~
tar -xf /path/to/export/file/zulip-export-zcmpxfm6.tar.gz
cd /home/zulip/deployments/current
./manage.py import '' ~/zulip-export-zcmpxfm6
# supervisorctl start all # Starts the Zulip server
# ./manage.py reactivate_realm -r ''  # Reactivates the organization
```

This could take several minutes to run, depending on how much data you're
importing.

**Import options**

The commands above create an imported organization on the root domain
(`EXTERNAL_HOST`) of the Zulip installation. You can also import into a
custom subdomain, e.g. if you already have an existing organization on the
root domain. Replace the last two lines above with the following, after replacing
`<subdomain>` with the desired subdomain.

```
./manage.py import <subdomain> ~/zulip-export-zcmpxfm6
./manage.py reactivate_realm -r <subdomain>  # Reactivates the organization
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
