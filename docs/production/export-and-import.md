# Backups, export and import

Zulip has high quality export and import tools that can be used to
move data from one Zulip server to another, do backups, compliance
work, or migrate from your own servers to the hosted Zulip Cloud
service (or back):

* The [Backup](#backups) tool is designed for exact restoration of a
  Zulip server's state, for disaster recovery, testing with production
  data, or hardware migration.  This tool has a few limitations:

  * Backups must be restored on a server running the same Zulip
    version (most precisely, one where `manage.py showmigrations` has
    the same output).
  * Backups must be restored on a server running the same PostgreSQL
    version.
  * Backups aren't useful for migrating organizations between
    self-hosting and Zulip Cloud (which may require renumbering all
    the users/messages/etc.).

  We highly recommend this tool in situations where it is applicable,
  because it is highly optimized and highly stable, since the hard
  work is done by the built-in backup feature of PostgreSQL.  We also
  document [backup details](#backup-details) for users managing
  backups manually.

* The logical [Data export](#data-export) tool is designed for
  migrating data between Zulip Cloud and other Zulip servers, as well
  as various auditing purposes.  The logical export tool produces a
  `.tar.gz` archive with most of the Zulip database data encoded in
  JSON files–a format shared by our [data
  import](#import-into-a-new-zulip-server) tools for third-party
  services like
  [Slack](https://zulip.com/help/import-from-slack).

  Like the backup tool, logical data exports must be imported on a
  Zulip server running the same version.  However, logical data
  exports can be imported on Zulip servers running a different
  PostgreSQL version or hosting a different set of Zulip
  organizations.  We recommend this tool in cases where the backup
  tool isn't applicable, including situations where an easily
  machine-parsable export format is desired.

* Zulip also has an [HTML archive
  tool](https://github.com/zulip/zulip-archive), which is primarily
  intended for public archives, but can also be useful to
  inexpensively preserve public stream conversations when
  decommissioning a Zulip organization.

* It's possible to set up [PostgreSQL streaming
  replication](#postgresql-streaming-replication) and the [S3 file
  upload
  backend](../production/upload-backends.html#s3-backend-configuration)
  as part of a high evailability environment.

## Backups

The Zulip server has a built-in backup tool:

```
# As the zulip user
/home/zulip/deployments/current/manage.py backup
# Or as root
su zulip -c '/home/zulip/deployments/current/manage.py backup'
```

The backup tool provides the following options:
- `--output=/tmp/backup.tar.gz`: Filename to write the backup tarball
  to (default: write to a file in `/tmp`).  On success, the
  console output will show the path to the output tarball.
- `--skip-db`: Skip backup of the database.  Useful if you're using a
  remote PostgreSQL host with its own backup system and just need to
  backup non-database state.
- `--skip-uploads`: If `LOCAL_UPLOADS_DIR` is set, user-uploaded files
  in that directory will be ignored.

This will generate a `.tar.gz` archive containing all the data stored
on your Zulip server that would be needed to restore your Zulip
server's state on another machine perfectly.

### Restoring backups

First, [install a new Zulip server through Step 3][install-server]
with the same version of both the base OS and Zulip from your previous
installation.  Then, run as root:

```
/home/zulip/deployments/current/scripts/setup/restore-backup /path/to/backup
```

When that finishes, your Zulip server should be fully operational again.

#### Changing the hostname

It's common, when testing backup restoration, to restore backups with a
different user-facing hostname than the original server to avoid
disrupting service (e.g. `zuliptest.example.com` rather than
`zulip.example.com`).

If you do so, just like any other time you change the hostname, you'll
need to [update `EXTERNAL_HOST`](../production/settings.md) and then
restart the Zulip server (after backup restoration completes).

Until you do, your Zulip server will think its user-facing hostname is
still `zulip.example.com` and will return HTTP `400 BAD REQUEST`
errors when trying to access it via `zuliptest.example.com`.

#### Inspecting a backup tarball

If you're not sure what versions were in use when a given backup was
created, you can get that information via the files in the backup
tarball: `postgres-version`, `os-version`, and `zulip-version`.  The
following command may be useful for viewing these files without
extracting the entire archive.

```
tar -Oaxf /path/to/archive/zulip-backup-rest.tar.gz zulip-backup/zulip-version
```

[install-server]: ../production/install.md

### What is included

Backups contain everything you need to fully restore your Zulip
server, including the database, settings, secrets from
`/etc/zulip`, and user-uploaded files stored on the Zulip server.

The following data is not included in these backup archives,
and you may want to backup separately:

* The server access/error logs from `/var/log/zulip`.  The Zulip
  server only appends to logs, and they can be very large compared to
  the rest of the data for a Zulip server.

* Files uploaded with the Zulip
  [S3 file upload backend](../production/upload-backends.md).  We
  don't include these for two reasons. First, the uploaded file data
  in S3 can easily be many times larger than the rest of the backup,
  and downloading it all to a server doing a backup could easily
  exceed its disk capacity.  Additionally, S3 is a reliable persistent
  storage system with its own high-quality tools for doing backups.

* SSL certificates.  These are not included because they are
  particularly security-sensitive and are either trivially replaced
  (if generated via Certbot) or provided by the system administrator.

For completeness, Zulip's backups do not include certain highly
transient state that Zulip doesn't store in a database.  For example,
typing status data, API rate-limiting counters, and RabbitMQ queues
that are essentially always empty in a healthy server (like outgoing
emails to send).  You can check whether these queues are empty using
`rabbitmqctl list_queues`.

#### Backup details

This section is primarily for users managing backups themselves
(E.g. if they're using a remote PostgreSQL database with an existing
backup strategy), and also serves as documentation for what is
included in the backups generated by Zulip's standard tools.  The
data includes:

* The PostgreSQL database.  You can back this up with any standard
database export or backup tool.  Zulip has built-in support for taking
daily incremental backups using
[wal-g](https://github.com/wal-g/wal-g); these backups are stored for
30 days in S3.  If you have an Amazon S3 bucket you wish to store for
storing the backups, edit `/etc/zulip/zulip-secrets.conf` on the
PostgreSQL server to add:

    ```
    s3_backups_key = # aws public key
    s3_backups_secret_key =  # aws secret key
    s3_backups_bucket = # name of S3 backup
    ```

    After adding the secrets, run
    `/home/zulip/deployments/current/scripts/zulip-puppet-apply`.  You
    can (and should) monitor that backups are running regularly via
    the Nagios plugin installed into
    `/usr/lib/nagios/plugins/zulip_postgresql_backups/check_postgresql_backup`.

* Any user-uploaded files.  If you're using S3 as storage for file
uploads, this is backed up in S3. But if you have instead set
`LOCAL_UPLOADS_DIR`, any files uploaded by users (including avatars)
will be stored in that directory and you'll want to back it up.

* Your Zulip configuration including secrets from `/etc/zulip/`.
E.g. if you lose the value of `secret_key`, all users will need to
log in again when you set up a replacement server since you won't be
able to verify their cookies. If you lose `avatar_salt`, any
user-uploaded avatars will need to be re-uploaded (since avatar
filenames are computed using a hash of `avatar_salt` and user's
email), etc.

[export-import]: ../production/export-and-import.md

### Restore from manual backups

To restore from a manual backup, the process is basically the reverse of the above:

* Install new server as normal by downloading a Zulip release tarball
  and then using `scripts/setup/install`. You don't need
  to run the `initialize-database` second stage which puts default
  data into the database.

* Unpack to `/etc/zulip` the `settings.py` and `zulip-secrets.conf` files
  from your backups.

* If you ran `initialize-database` anyway above, you'll want to run
  `scripts/setup/postgres-init-db` to drop the initial database first.

* Restore your database from the backup.

* Reconfigure rabbitmq to use the password from `secrets.conf`
  by running, as root, `scripts/setup/configure-rabbitmq`.

* If you're using local file uploads, restore those files to the path
  specified by `settings.LOCAL_UPLOADS_DIR` and (if appropriate) any
  logs.

* Start the server using `scripts/restart-server`.

This restoration process can also be used to migrate a Zulip
installation from one server to another.

We recommend running a disaster recovery after setting up your backups to
confirm that your backups are working. You may also want to monitor
that they are up to date using the Nagios plugin at:
`puppet/zulip/files/nagios_plugins/zulip_postgresql_backups/check_postgresql_backup`.

## PostgreSQL streaming replication

Zulip has database configuration for using PostgreSQL streaming
replication. You can see the configuration in these files:

* `puppet/zulip_ops/manifests/profile/postgresql.pp`
* `puppet/zulip_ops/files/postgresql/*`

We use this configuration for Zulip Cloud, and it works well in
production, but it's not fully generic.  Contributions to make it a
supported and documented option for other installations are
appreciated.

## Data export

Zulip's powerful data export tool is designed to handle migration of a
Zulip organization between different hardware platforms; as a result,
these exports contain all non-transient data for a Zulip organization,
with the exception of passwords and API keys.

We recommend using the [backup tool](#backups) if your primary goal is
backups.

### Preventing changes during the export

For best results, you'll want to shut down access to the organization
before exporting; so that nobody can send new messages (etc.)  while
you're exporting data.  There are two ways to do this:

1. `supervisorctl stop all`, which stops the whole server.  This is
preferred if you're not hosting multiple organizations, because it has
no side effects other than disabling the Zulip server for the
duration.
1. Pass `--deactivate` to `./manage export`, which first deactivates
the target organization, logging out all active login sessions and
preventing all accounts from logging in or accessing the API.  This is
preferred for environments like Zulip Cloud where you might want to
export a single organization without disrupting any other users, and
the intent is to move hosting of the organization (and forcing users
to re-log in would be required as part of the hosting migration
anyway).

We include both options in the instructions below, commented out so
that neither runs (using the `# ` at the start of the lines).  If
you'd like to use one of these options, remove the `# ` at the start
of the lines for the appropriate option.

### Export your Zulip data

Log in to a shell on your Zulip server as the `zulip` user. Run the
following commands:

```
cd /home/zulip/deployments/current
# supervisorctl stop all                  # Stops the Zulip server
# export DEACTIVATE_FLAG="--deactivate"   # Deactivates the organization
./manage.py export -r '' $DEACTIVATE_FLAG # Exports the data
```

(The `-r` option lets you specify the organization to export; `''` is
the default organization hosted at the Zulip server's root domain.)

This will generate a tarred archive with a name like
`/tmp/zulip-export-zcmpxfm6.tar.gz`.  The archive contains several
JSON files (containing the Zulip organization's data) as well as an
archive of all the organization's uploaded files.

## Import into a new Zulip server

1. [Install a new Zulip server](../production/install.md),
**skipping Step 3** (you'll create your Zulip organization via the data
 import tool instead).
    * Ensure that the Zulip server you're importing into is running the same
      version of Zulip as the server you're exporting from.

    * For exports from Zulip Cloud (zulip.com), you need to [upgrade to
      master][upgrade-zulip-from-git], since we run run master on
      Zulip Cloud:

      ```
      /home/zulip/deployments/current/scripts/upgrade-zulip-from-git master
      ```

      It is not sufficient to be on the latest stable release, as
      zulip.com runs pre-release versions of Zulip that are often
      several months of development ahead of the latest release.

    * Note that if your server has limited free RAM, you'll want to
      shut down the Zulip server with `supervisorctl stop all` while
      you run the import, since our minimal system requirements do not
      budget extra RAM for running the data import tool.

2. If your new Zulip server is meant to fully replace a previous Zulip
server, you may want to copy some settings from `/etc/zulip` to your
new server to reuse the server-level configuration and secret keys
from your old server.  There are a few important details to understand
about doing so:

   * Copying `/etc/zulip/settings.py` and `/etc/zulip/zulip.conf` is
     safe and recommended.  Care is required when copying secrets from
     `/etc/zulip/zulip-secrets.conf` (details below).
   * If you copy `zulip_org_id` and `zulip_org_key` (the credentials
     for the [mobile push notifications
     service](../production/mobile-push-notifications.md)), you should
     be very careful to make sure the no users had their IDs
     renumbered during the import process (this can be checked using
     `manage.py shell` with some care).  The push notifications
     service has a mapping of which `user_id` values are associated
     with which devices for a given Zulip server (represented by the
     `zulip_org_id` registration).  This means that if any `user_id`
     values were renumbered during the import and you don't register a
     new `zulip_org_id`, push notifications meant for the user who now
     has ID 15 may be sent to devices registered by the user who had
     user ID 15 before the data export (yikes!).  The solution is
     simply to not copy these settings and re-register your server for
     mobile push notifications if any users had their IDs renumbered
     during the logical export/import process.
   * If you copy the `rabbitmq_password` secret from
     `zulip-secrets.conf`, you'll need to run
     `scripts/setup/configure-rabbitmq` to update your local RabbitMQ
     installation to use the password in your Zulip secrets file.
   * You will likely want to copy `camo_key` (required to avoid
     breaking certain links) and any settings you added related to
     authentication and email delivery so that those work on your new
     server.
   * Copying `avatar_salt` is not recommended, due to similar issues
     to the mobile push notifications service.  Zulip will
     automatically rewrite avatars at URLs appropriate for the new
     user IDs, and using the same avatar salt (and same server URL)
     post import could result in issues with browsers caching the
     avatar image improperly for users whose ID was renumbered.

3. Log in to a shell on your Zulip server as the `zulip` user. Run the
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

This could take several minutes to run depending on how much data you're
importing.

[upgrade-zulip-from-git]: ../production/upgrade-or-modify.html#upgrading-from-a-git-repository

#### Import options

The commands above create an imported organization on the root domain
(`EXTERNAL_HOST`) of the Zulip installation. You can also import into a
custom subdomain, e.g. if you already have an existing organization on the
root domain. Replace the last three lines above with the following, after replacing
`<subdomain>` with the desired subdomain.

```
./manage.py import <subdomain> ~/zulip-export-zcmpxfm6
./manage.py reactivate_realm -r <subdomain>  # Reactivates the organization
```

### Logging in

Once the import completes, all your users will have accounts in your
new Zulip organization, but those accounts won't have passwords yet
(since for security reasons, passwords are not exported).
Your users will need to either authenticate using something like
Google auth or start by resetting their passwords.

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

### Deleting and re-importing

If you did a test import of a Zulip organization, you may want to
delete the test import data from your Zulip server before doing a
final import.  You can **permanently delete** all data from a Zulip
organization using the following procedure:

* Start a [Zulip management shell](../production/management-commands.html#manage-py-shell)
* In the management shell, run the following commands, replacing `""`
  with the subdomain if [you are hosting the organization on a
  subdomain](../production/multiple-organizations.md):

```
realm = Realm.objects.get(string_id="")
realm.delete()
```

The output contains details on the objects deleted from the database.

Now, exit the management shell and run this to clear Zulip's cache:
```
/home/zulip/deployments/current/scripts/setup/flush-memcached
```

Assuming you're using the
[local file uploads backend](../production/upload-backends.md), you
can additionally delete all file uploads, avatars, and custom emoji on
a Zulip server (across **all organizations**) with the following
command:

```
rm -rf /home/zulip/uploads/*/*
```

If you're hosting multiple organizations and would like to remove
uploads from a single organization, you'll need to access `realm.id`
in the management shell before deleting the organization from the
database (this will be `2` for the first organization created on a
Zulip server, shown in the example below), e.g.:

```
rm -rf /home/zulip/uploads/*/2/
```

Once that's done, you can simply re-run the import process.
