# Secure, maintain, and upgrade

This page covers topics that will help you maintain a healthy, up-to-date, and
secure Zulip installation, including:

- [Upgrading](#upgrading)
- [Upgrading from a git repository](#upgrading-from-a-git-repository)
- [Backups](#backups)
- [Monitoring](#monitoring)
- [Scalability](#scalability)
- [Management commands](#management-commands)

You may also want to read this related content:

- [Security Model](security-model.html)

## Upgrading

**We recommend reading this entire section before doing your first
upgrade.**

To upgrade to a new version of the zulip server, download the appropriate
release tarball from <https://www.zulip.org/dist/releases/>.

You also have the option of creating your own release tarballs from a
copy of the [zulip.git repository](https://github.com/zulip/zulip)
using `tools/build-release-tarball` or upgrade Zulip
[to a version in a Git repository directly](#upgrading-from-a-git-repository).

Next, run as root:

```
/home/zulip/deployments/current/scripts/upgrade-zulip zulip-server-VERSION.tar.gz
```

The upgrade process will shut down the Zulip service and then run `apt-get upgrade`, a
puppet apply, any database migrations, and then bring the Zulip service back
up. Upgrading will result in some brief downtime for the service, which should be
under 30 seconds unless there is an expensive transition involved. Unless you
have tested the upgrade in advance, we recommend doing upgrades at off hours.

Note that upgrading an existing Zulip production server from Ubuntu
14.04 Trusty to Ubuntu 16.04 Xenial will require significant manual
intervention on your part to migrate the data in the database from
Postgres 9.3 to Postgres 9.5.  Contributions on testing and
documenting this process are welcome!

### Preserving local changes to configuration files

**Warning**: If you have modified configuration files installed by
Zulip (e.g. the nginx configuration), the Zulip upgrade process will
overwrite your configuration when it does the `puppet apply`.

You can test whether this will happen assuming no upstream changes to
the configuration using `scripts/zulip-puppet-apply` (without the
`-f` option), which will do a test puppet run and output and changes
it would make. Using this list, you can save a copy of any files
that you've modified, do the upgrade, and then restore your
configuration.

If you need to do this, please report the issue so
that we can make the Zulip puppet configuration flexible enough to
handle your setup.

### Troubleshooting with the upgrade log

The Zulip upgrade script automatically logs output to
`/var/log/zulip/upgrade.log`. Please use those logs to include output
that shows all errors in any bug reports.

After the upgrade, we recommend checking `/var/log/zulip/errors.log`
to confirm that your users are not experiencing errors after the
upgrade.

### Rolling back to a prior version

The Zulip upgrade process works by creating a new deployment under
`/home/zulip/deployments/` containing a complete copy of the Zulip server code,
and then moving the symlinks at `/home/zulip/deployments/{current,last,next}`
as part of the upgrade process.

This means that if the new version isn't working,
you can quickly downgrade to the old version by running
`/home/zulip/deployments/last/scripts/restart-server`, or to an
earlier previous version by running
`/home/zulip/deployments/DATE/scripts/restart-server`.  The
`restart-server` script stops any running Zulip server, and starts
the version corresponding to the `restart-server` path you call.

### Updating settings

If required, you can update your settings by editing `/etc/zulip/settings.py`
and then run `/home/zulip/deployments/current/scripts/restart-server` to
restart the server.

### Applying Ubuntu system updates

While the Zulip upgrade script runs `apt-get upgrade`, you are responsible for
running this on your system on a regular basis between Zulip upgrades to
ensure that it is up to date with the latest security patches.

### API and your Zulip URL

To use the Zulip API with your Zulip server, you will need to use the
API endpoint of e.g. `https://zulip.example.com/api`.  Our Python
API example scripts support this via the
`--site=https://zulip.example.com` argument.  The API bindings
support it via putting `site=https://zulip.example.com` in your
.zuliprc.

Every Zulip integration supports this sort of argument (or e.g. a
`ZULIP_SITE` variable in a zuliprc file or the environment), but this
is not yet documented for some of the integrations (the included
integration documentation on `/integrations` will properly document
how to do this for most integrations).  We welcome pull requests for
integrations that don't discuss this!

Similarly, you will need to instruct your users to specify the URL
for your Zulip server when using the Zulip desktop and mobile apps.

### Memory leak mitigation

As a measure to mitigate the impact of potential memory leaks in one
of the Zulip daemons, the service automatically restarts itself
every Sunday early morning.  See `/etc/cron.d/restart-zulip` for the
precise configuration.

## Upgrading from a git repository

Starting with version 1.4, the Zulip server supports upgrading to a
commit in Git.  You can configure the `git` repository that you'd like
to use by adding a section like this to `/etc/zulip/zulip.conf`; by
default it uses the main `zulip` repository (shown below).

```
[deployment]
git_repo_url = https://github.com/zulip/zulip.git
```

Once that is done (and assuming the currently installed version of
Zulip is 1.7 or newer), you can do deployments by running as root:

```
/home/zulip/deployments/current/scripts/upgrade-zulip-from-git <branch>
```

and Zulip will automatically fetch the relevant branch from the
specified repository to a directory under `/home/zulip/deployments`
(where release tarball are unpacked), build the compiled static assets
from source, and switches to the new version.

### Upgrading from Zulip 1.6 and older

If you're currently using Zulip older than 1.7, you will need to
add `zulip::static_asset_compiler` to your `/etc/zulip/zulip.conf`
file's `puppet_classes` entry, like this:

```
puppet_classes = zulip::voyager, zulip::static_asset_compiler
```

Then, run `scripts/zulip-puppet-apply` to install the dependencies for
building Zulip's static assets.  Once you've upgraded to Zulip 1.7 or
above, you can safely remove `zulip::static_asset_compiler` from
`puppet_classes` to clean it up; in Zulip 1.7 and above, it is a
dependency of `zulip::voyager`.

## Backups

There are several pieces of data that you might want to back up:

* The postgres database.  That you can back up like any postgres
database; we have some example tooling for doing that incrementally
into S3 using [wal-e](https://github.com/wal-e/wal-e) in
`puppet/zulip_internal/manifests/postgres_common.pp` (that's what we
use for zulip.com's database backups).  Note that this module isn't
part of the Zulip server releases since it's part of the zulip.com
configuration (see <https://github.com/zulip/zulip/issues/293>
for a ticket about fixing this to make life easier for running
backups).

* Any user-uploaded files.  If you're using S3 as storage for file
uploads, this is backed up in S3, but if you have instead set
`LOCAL_UPLOADS_DIR`, any files uploaded by users (including avatars)
will be stored in that directory and you'll want to back it up.

* Your Zulip configuration including secrets from `/etc/zulip/`.
E.g. if you lose the value of `secret_key`, all users will need to
login again when you setup a replacement server since you won't be
able to verify their cookies; if you lose `avatar_salt`, any
user-uploaded avatars will need to be re-uploaded (since avatar
filenames are computed using a hash of `avatar_salt` and user's
email), etc.

* The logs under `/var/log/zulip` can be handy to have backed up, but
they do get large on a busy server, and it's definitely
lower-priority.

If you are interested in backups because you are moving from one Zulip
server to another server and can't transfer a full postgres dump
(which is definitely the simplest approach), our draft
[conversion and export design document](conversion.html) may help.
The tool is well designed and was tested carefully with dozens of
realms as of mid-2016 but is not integrated into Zulip's regular
testing process, and thus it is worth asking on the Zulip developers
mailing list whether it needs any minor updates to do things like
export newly added tables.

### Restore from backups

To restore from backups, the process is basically the reverse of the above:

* Install new server as normal by downloading a Zulip release tarball
  and then using `scripts/setup/install`, you don't need
  to run the `initialize-database` second stage which puts default
  data into the database.

* Unpack to `/etc/zulip` the `settings.py` and `zulip-secrets.conf` files
  from your backups.

* Restore your database from the backup using `wal-e`; if you ran
  `initialize-database` anyway above, you'll want to first
  `scripts/setup/postgres-init-db` to drop the initial database first.

* Reconfigure rabbitmq to use the password from `secrets.conf`
  by running, as root, `scripts/setup/configure-rabbitmq`.

* If you're using local file uploads, restore those files to the path
  specified by `settings.LOCAL_UPLOADS_DIR` and (if appropriate) any
  logs.

* Start the server using `scripts/restart-server`.

This restoration process can also be used to migrate a Zulip
installation from one server to another.

We recommend running a disaster recovery after you setup backups to
confirm that your backups are working; you may also want to monitor
that they are up to date using the Nagios plugin at:
`puppet/zulip_internal/files/nagios_plugins/check_postgres_backup`.

Contributions to more fully automate this process or make this section
of the guide much more explicit and detailed are very welcome!


### Postgres streaming replication

Zulip has database configuration for using Postgres streaming
replication; you can see the configuration in these files:

* `puppet/zulip_internal/manifests/postgres_slave.pp`
* `puppet/zulip_internal/manifests/postgres_master.pp`
* `puppet/zulip_internal/files/postgresql/*`

Contribution of a step-by-step guide for setting this up (and moving
this configuration to be available in the main `puppet/zulip/` tree)
would be very welcome!

## Monitoring

The complete Nagios configuration (sans secret keys) used to
monitor zulip.com is available under `puppet/zulip_internal` in the
Zulip Git repository (those files are not installed in the release
tarballs).

The Nagios plugins used by that configuration are installed
automatically by the Zulip installation process in subdirectories
under `/usr/lib/nagios/plugins/`.  The following is a summary of the
various Nagios plugins included with Zulip and what they check:

Application server and queue worker monitoring:

* `check_send_receive_time` (sends a test message through the system
  between two bot users to check that end-to-end message sending works)

* `check_rabbitmq_consumers` and `check_rabbitmq_queues` (checks for
  rabbitmq being down or the queue workers being behind)

* `check_queue_worker_errors` (checks for errors reported by the queue
  workers)

* `check_worker_memory` (monitors for memory leaks in queue workers)

* `check_email_deliverer_backlog` and `check_email_deliverer_process`
  (monitors for whether outgoing emails are being sent)

Database monitoring:

* `check_postgres_replication_lag` (checks streaming replication is up
  to date).

* `check_postgres` (checks the health of the postgres database)

* `check_postgres_backup` (checks backups are up to date; see above)

* `check_fts_update_log` (monitors for whether full-text search updates
  are being processed)

Standard server monitoring:

* `check_website_response.sh` (standard HTTP check)

* `check_debian_packages` (checks apt repository is up to date)

If you're using these plugins, bug reports and pull requests to make
it easier to monitor Zulip and maintain it in production are
encouraged!

## Scalability

This section attempts to address the considerations involved with
running Zulip with larger teams (especially >1000 users).

* For an organization with 100+ users, it's important to have more
  than 4GB of RAM on the system.  Zulip will install on a system with
  2GB of RAM, but with less than 3.5GB of RAM, it will run its
  [queue processors](queuing.html) multithreaded to conserve memory;
  this creates a significant performance bottleneck.

* [chat.zulip.org](chat-zulip-org.html), with thousands of user
  accounts and thousands of messages sent every week, has 8GB of RAM,
  4 cores, and 80GB of disk.  The CPUs are essentially always idle,
  but the 8GB of RAM is important.

* We recommend using a [remote postgres
  database](prod-postgres.html) for isolation, though it is
  not required.  In the following, we discuss a relatively simple
  configuration with two types of servers: application servers
  (running Django, Tornado, RabbitMQ, Redis, Memcached, etc.) and
  database servers.

* You can scale to a pretty large installation (O(~1000) concurrently
  active users using it to chat all day) with just a single reasonably
  large application server (e.g. AWS c3.2xlarge with 8 cores and 16GB
  of RAM) sitting mostly idle (<10% CPU used and only 4GB of the 16GB
  RAM actively in use).  You can probably get away with half that
  (e.g. c3.xlarge), but ~8GB of RAM is highly recommended at scale.
  Beyond a 1000 active users, you will eventually want to increase the
  memory cap in `memcached.conf` from the default 512MB to avoid high
  rates of memcached misses.

* For the database server, we highly recommend SSD disks, and RAM is
  the primary resource limitation.  We have not aggressively tested
  for the minimum resources required, but 8 cores with 30GB of RAM
  (e.g. AWS's m3.2xlarge) should suffice; you may be able to get away
  with less especially on the CPU side.  The database load per user is
  pretty optimized as long as `memcached` is working correctly.  This
  has not been tested, but from extrapolating the load profile, it
  should be possible to scale a Zulip installation to 10,000s of
  active users using a single large database server without doing
  anything complicated like sharding the database.

* For reasonably high availability, it's easy to run a hot spare
  application server and a hot spare database (using Postgres
  streaming replication; see the section on configuring this).  Be
  sure to check out the section on backups if you're hoping to run a
  spare application server; in particular you probably want to use the
  S3 backend for storing user-uploaded files and avatars and will want
  to make sure secrets are available on the hot spare.

* Zulip does not support dividing traffic for a given Zulip realm
  between multiple application servers.  There are two issues: you
  need to share the memcached/Redis/RabbitMQ instance (these should
  can be moved to a network service shared by multiple servers with a
  bit of configuration) and the Tornado event system for pushing to
  browsers currently has no mechanism for multiple frontend servers
  (or event processes) talking to each other.  One can probably get a
  factor of 10 in a single server's scalability by [supporting
  multiple tornado processes on a single
  server](https://github.com/zulip/zulip/issues/372), which is also
  likely the first part of any project to support exchanging events
  amongst multiple servers.

Questions, concerns, and bug reports about this area of Zulip are very
welcome!  This is an area we are hoping to improve.

## Securing your Zulip server

Zulip's security model is discussed in
[a separate document](security-model.html).

## Management commands

Zulip has a large library of [Django management
commands](https://docs.djangoproject.com/en/1.8/ref/django-admin/#django-admin-and-manage-py).
To use them, you will want to be logged in as the `zulip` user and for
the purposes of this documentation, we assume the current working
directory is `/home/zulip/deployments/current`.

Below, we show several useful examples, but there are more than 100
in total.  We recommend skimming the usage docs (or if there are none,
the code) of a management command before using it, since they are
generally less polished and more designed for expert use than the rest
of the Zulip system.

### manage.py shell

You can get an iPython shell with full access to code within the Zulip
project using `manage.py shell`, e.g., you can do the following to
change an email address:

```
$ /home/zulip/deployments/current/manage.py shell
In [1]: user_profile = get_user_profile_by_email("email@example.com")
In [2]: do_change_user_email(user_profile, "new_email@example.com")
```

#### manage.py dbshell

This will start a postgres shell connected to the Zulip database.

### Grant administrator access

You can make any user a realm administrator on the command line with
the `knight` management command:

```
./manage.py knight username@example.com -f
```

#### Creating API super users with manage.py

If you need to manage the IRC, Jabber, or Zephyr mirrors, you will
need to create API super users.  To do this, use `./manage.py knight`
with the `--permission=api_super_user` argument.  See the respective
integration scripts for these mirrors (under
[`zulip/integrations/`][integrations-source] in the [Zulip Python API
repo][python-api-repo]) for further detail on these.

[integrations-source]: https://github.com/zulip/python-zulip-api/tree/master/zulip/integrations
[python-api-repo]: https://github.com/zulip/python-zulip-api

#### Exporting users and realms with manage.py export

If you need to do an export of a single user or of an entire realm, we
have tools in `management/` that essentially export Zulip data to the
file system.

`export_single_user.py` exports the message history and realm-public
metadata for a single Zulip user (including that user's *received*
messages as well as their sent messages).

A good overview of the process for exporting a single realm when
moving a realm to a new server (without moving a full database dump)
is in
[management/export.py](https://github.com/zulip/zulip/blob/master/zerver/management/commands/export.py). We
recommend you read the comment there for words of wisdom on speed,
what is and is not exported, what will break upon a move to a new
server, and suggested procedure.

### Other useful manage.py commands

There are a large number of useful management commands under
`zerver/management/commands/`; you can also see them listed using
`./manage.py` with no arguments.

## Hosting multiple Zulip organizations

This is explained in detail on [its own page](prod-multiple-organizations.html).
