# Secure, maintain, and upgrade

This page covers topics that will help you maintain a healthy, up-to-date, and
secure Zulip installation, including:

- [Upgrading](#upgrading)
- [Upgrading from a git repository](#upgrading-from-a-git-repository)
- [Backups](#backups)
- [Monitoring](#monitoring)
- [Scalability](#scalability)
- [Security Model](#security-model)
- [Management commands](#management-commands)


## Upgrading

**We recommend reading this entire section before doing your first
upgrade.**

To upgrade to a new version of the zulip server, download the appropriate
release tarball from
[https://www.zulip.com/dist/releases/](https://www.zulip.com/dist/releases/)

You also have the option of creating your own release tarballs from a
copy of zulip.git repository using `tools/build-release-tarball`. And,
starting with Zulip version 1.4, you can upgrade Zulip [to a version
in a Git repository directly](#upgrade-from-a-git-repository).

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
and then moving the symlinks at `/home/zulip/deployments/current` and
`/root/zulip` as part of the upgrade process.

This means that if the new version isn't working,
you can quickly downgrade to the old version by using
`/home/zulip/deployments/<date>/scripts/restart-server` to return to
a previous version that you've deployed (the version is specified
via the path to the copy of `restart-server` you call).

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

Starting with version 1.4, the Zulip server supports doing deployments
from a Git repository.  To configure this, you will need to add
`zulip::static_asset_compiler` to your `/etc/zulip/zulip.conf` file's
`puppet_classes` entry, like this:

```
puppet_classes = zulip::voyager, zulip::static_asset_compiler
```

Then, run `scripts/zulip-puppet-apply` to install the dependencies for
building Zulip's static assets.  You can configure the `git`
repository that you'd like to use by adding a section like this to
`/etc/zulip/zulip.conf`; by default it uses the main `zulip`
repository (shown below).

```
[deployment]
git_repo_url = https://github.com/zulip/zulip.git
```

Once that is done (and assuming the currently installed version of
Zulip is new enough that this script exists), you can do deployments
by running as root:

```
/home/zulip/deployments/current/scripts/upgrade-zulip-from-git <branch>
```

and Zulip will automatically fetch the relevant branch from the
specified repository, build the static assets, and deploy that
version.  Currently, the upgrade process is slow, but it doesn't need
to be; there is ongoing work on optimizing it.

## Backups

There are several pieces of data that you might want to back up:

* The postgres database.  That you can back up like any postgres
database; we have some example tooling for doing that incrementally
into S3 using [wal-e](https://github.com/wal-e/wal-e) in
`puppet/zulip_internal/manifests/postgres_common.pp` (that's what we
use for zulip.com's database backups).  Note that this module isn't
part of the Zulip server releases since it's part of the zulip.com
configuration (see https://github.com/zulip/zulip/issues/293 for a
ticket about fixing this to make life easier for running backups).

* Any user-uploaded files.  If you're using S3 as storage for file
uploads, this is backed up in S3, but if you have instead set
LOCAL_UPLOADS_DIR, any files uploaded by users (including avatars)
will be stored in that directory and you'll want to back it up.

* Your Zulip configuration including secrets from /etc/zulip/.
E.g. if you lose the value of secret_key, all users will need to login
again when you setup a replacement server since you won't be able to
verify their cookies; if you lose avatar_salt, any user-uploaded
avatars will need to be re-uploaded (since avatar filenames are
computed using a hash of avatar_salt and user's email), etc.

* The logs under /var/log/zulip can be handy to have backed up, but
they do get large on a busy server, and it's definitely
lower-priority.

### Restore from backups

To restore from backups, the process is basically the reverse of the above:

* Install new server as normal by downloading a Zulip release tarball
  and then using `scripts/setup/install`, you don't need
  to run the `initialize-database` second stage which puts default
  data into the database.

* Unpack to /etc/zulip the settings.py and secrets.conf files from your backups.

* Restore your database from the backup using wal-e; if you ran
  `initialize-database` anyway above, you'll want to first
  `scripts/setup/postgres-init-db` to drop the initial database first.

* If you're using local file uploads, restore those files to the path
  specified by `settings.LOCAL_UPLOADS_DIR` and (if appropriate) any
  logs.

* Start the server using scripts/restart-server

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

* puppet/zulip_internal/manifests/postgres_slave.pp
* puppet/zulip_internal/manifests/postgres_master.pp
* puppet/zulip_internal/files/postgresql/*

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

* check_send_receive_time (sends a test message through the system
  between two bot users to check that end-to-end message sending works)

* check_rabbitmq_consumers and check_rabbitmq_queues (checks for
  rabbitmq being down or the queue workers being behind)

* check_queue_worker_errors (checks for errors reported by the queue workers)

* check_worker_memory (monitors for memory leaks in queue workers)

* check_email_deliverer_backlog and check_email_deliverer_process
  (monitors for whether outgoing emails are being sent)

Database monitoring:

* check_postgres_replication_lag (checks streaming replication is up
  to date).

* check_postgres (checks the health of the postgres database)

* check_postgres_backup (checks backups are up to date; see above)

* check_fts_update_log (monitors for whether full-text search updates
  are being processed)

Standard server monitoring:

* check_website_response.sh (standard HTTP check)

* check_debian_packages (checks apt repository is up to date)

If you're using these plugins, bug reports and pull requests to make
it easier to monitor Zulip and maintain it in production are
encouraged!

## Scalability

This section attempts to address the considerations involved with
running Zulip with a large team (>1000 users).

* We recommend using a [remote postgres
  database](#postgres-database-details) for isolation, though it is
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
  need to share the memcached/redis/rabbitmq instance (these should
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

## Security Model

This section attempts to document the Zulip security model.  Since
this is new documentation, it likely does not cover every issue; if
there are details you're curious about, please feel free to ask
questions on the Zulip development mailing list (or if you think
you've found a security bug, please report it to
security@googlegroups.com so we can do a responsible security
announcement).

### Secure your Zulip server like your email server

* It's reasonable to think about security for a Zulip server like you
  do security for a team email server -- only trusted administrators
  within an organization should have shell access to the server.

  In particular, anyone with root access to a Zulip application server
  or Zulip database server, or with access to the `zulip` user on a
  Zulip application server, has complete control over the Zulip
  installation and all of its data (so they can read messages, modify
  history, etc.).  It would be difficult or impossible to avoid this,
  because the server needs access to the data to support features
  expected of a group chat system like the ability to search the
  entire message history, and thus someone with control over the
  server has access to that data as well.

### Encryption and Authentication

* Traffic between clients (web, desktop and mobile) and the Zulip is
  encrypted using HTTPS.  By default, all Zulip services talk to each
  other either via a localhost connection or using an encrypted SSL
  connection.

* The preferred way to login to Zulip is using an SSO solution like
  Google Auth, LDAP, or similar.  Zulip stores user passwords using
  the standard PBKDF2 algorithm.  Password strength is checked and
  weak passwords are visually discouraged using the zxcvbn library,
  but Zulip does not by default have strong requirements on user
  password strength.  Modify `static/js/common.js` to adjust the
  password strength requirements (Patches welcome to make controlled
  by an easy setting!).

* Zulip requires CSRF tokens in all interactions with the web API to
  prevent CSRF attacks.

### Messages and History

* Zulip message content is rendering using a specialized Markdown
  parser which escapes content to protect against cross-site scripting
  attacks.

* Zulip supports both public streams and private ("invite-only")
  streams.  Any Zulip user can join any public stream in the realm
  (and can view the complete message of any public stream history
  without joining the stream).

* Users who are not members of a private stream cannot read messages
  on the stream, send messages to the stream, or join the stream, even
  if they are a Zulip administrator.  However, any member of a private
  stream can invite other users to the stream.  When a new user joins
  a private stream, they can see future messages sent to the stream,
  but they do not receive access to the stream's message history.

* Zulip supports editing the content or topics of messages that have
  already been sent (and even updating the topic of messages sent by
  other users when editing the topic of the overall thread).

  While edited messages are synced immediately to open browser
  windows, editing messages is not a safe way to redact secret content
  (e.g. a password) unintentionally shared via Zulip, because other
  users may have seen and saved the content of the original message
  (for example, they could have taken a screenshot immediately after
  you sent the message, or have an API tool recording all messages
  they receive).

  Zulip stores and sends to clients the content of every historical
  version of a message, so that future versions of Zulip could support
  displaying the diffs between previous versions.

### Users and Bots

* There are three types of users in a Zulip realm: Administrators,
  normal users, and bots.  Administrators have the ability to
  deactivate and reactivate other human and bot users, delete streams,
  add/remove administrator privileges, as well as change configuration
  for the overall realm (e.g. whether an invitation is required to
  join the realm).  Being a Zulip administrator does not provide the
  ability to interact with other users' private messages or the
  messages sent to private streams to which the administrator is not
  subscribed.  However, a Zulip administrator subscribed to a stream
  can toggle whether that stream is public or private.  Also, Zulip
  realm administrators have administrative access to the API keys of
  all bots in the realm, so a Zulip administrator may be able to
  access messages sent to private streams that have bots subscribed,
  by using the bot's credentials.

  In the future, Zulip's security model may change to allow realm
  administrators to access private messages (e.g. to support auditing
  functionality).

* Every Zulip user has an API key, available on the settings page.
  This API key can be used to do essentially everything the user can
  do; for that reason, users should keep their API key safe.  Users
  can rotate their own API key if it is accidentally compromised.

* To properly remove a user's access to a Zulip team, it does not
  suffice to change their password or deactivate their account in the
  SSO system, since neither of those prevents authenticating with the
  user's API key or those of bots the user has created.  Instead, you
  should deactivate the user's account in the Zulip administration
  interface (/#administration); this will automatically also
  deactivate any bots the user had created.

* The Zulip mobile apps authenticate to the server by sending the
  user's password and retrieving the user's API key; the apps then use
  the API key to authenticate all future interactions with the site.
  Thus, if a user's phone is lost, in addition to changing passwords,
  you should rotate the user's Zulip API key.

* Zulip bots are used for integrations.  A Zulip bot can do everything
  a normal user in the realm can do including reading other, with a
  few exceptions (e.g. a bot cannot login to the web application or
  create other bots).  In particular, with the API key for a Zulip
  bot, one can read any message sent to a public stream in that bot's
  realm.  A likely future feature for Zulip is [limited bots that can
  only send messages](https://github.com/zulip/zulip/issues/373).

* Certain Zulip bots can be marked as "API super users"; these special
  bots have the ability to send messages that appear to have been sent
  by another user (an important feature for implementing integrations
  like the Jabber, IRC, and Zephyr mirrors).

### User-uploaded content

* Zulip supports user-uploaded files; ideally they should be hosted
  from a separate domain from the main Zulip server to protect against
  various same-domain attacks (e.g. zulip-user-content.example.com)
  using the S3 integration.

  The URLs of user-uploaded files are secret; if you are using the
  "local file upload" integration, anyone with the URL of an uploaded
  file can access the file.  This means the local uploads integration
  is vulnerable to a subtle attack where if a user clicks on a link in
  a secret .PDF or .HTML file that had been uploaded to Zulip, access
  to the file might be leaked to the other server via the Referrer
  header (see https://github.com/zulip/zulip/issues/320).

  The Zulip S3 file upload integration is relatively safe against that
  attack, because the URLs of files presented to users don't host the
  content.  Instead, the S3 integration checks the user has a valid
  Zulip session in the relevant realm, and if so then redirects the
  browser to a one-time S3 URL that expires a short time later.
  Keeping the URL secret is still important to avoid other users in
  the Zulip realm from being able to access the file.

* Zulip supports using the Camo image proxy to proxy content like
  inline image previews that can be inserted into the Zulip message
  feed by other users over HTTPS.

* By default, Zulip will provide image previews inline in the body of
  messages when a message contains a link to an image.  You can
  control this using the `INLINE_IMAGE_PREVIEW` setting.

### Final notes and security response

If you find some aspect of Zulip that seems inconsistent with this
security model, please report it to zulip-security@googlegroups.com so that we can
investigate and coordinate an appropriate security release if needed.

Zulip security announcements will be sent to
zulip-announce@googlegroups.com, so you should subscribe if you are
running Zulip in production.

## Management commands

Zulip has a large library of [Django management
commands](https://docs.djangoproject.com/en/1.8/ref/django-admin/#django-admin-and-manage-py).
To use them, you will want to be logged in as the `zulip` user and for
the purposes of this documentation, we assume the current working
directory is `/home/zulip/deployments/current`.

Below, we should several useful examples, but there are more than 100
in total.  We recommend skimming the usage docs (or if there are none,
the code) of a management command before using it, since they are
generally less polished and more designed for expert use than the rest
of the Zulip system.

### manage.py shell

You can get an iPython shell with full access to code within the Zulip
project using `manage.py shell`, e.g. you can do the following to
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

#### Creating api super users with manage.py

If you need to manage the IRC, Jabber, or Zephyr mirrors, you will
need to create api super users.  To do this, use `./manage.py knight`
with the `--permission=api_super_user` argument.  See
`bots/irc-mirror.py` and `bots/jabber_mirror.py` for further detail on
these.


### Other useful manage.py commands

There are a large number of useful management commands under
`zerver/manangement/commands/`; you can also see them listed using
`./manage.py` with no arguments.

One such command worth highlighting because it's a valuable feature
with no UI in the Administration page is `./manage.py realm_filters`,
which allows you to configure certain patterns in messages to be
automatically linkified, e.g., whenever someone mentions "T1234", it
could be auto-linkified to ticket 1234 in your team's Trac instance.


Next: [Remote User SSO Authentication.](prod-remote-user-sso-auth.html)
