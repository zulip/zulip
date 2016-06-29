Zulip in production
===================

This documents the process for installing Zulip in a production environment.

Note that if you just want to play around with Zulip and see what it
looks like, it is easier to install it in a development environment
following the instructions in README.dev, since then you don't need to
worry about setting up SSL certificates and an authentication mechanism.

Recommended requirements:

* Server running Ubuntu Trusty
* At least 2 CPUs for production use with 100+ users
* At least 4GB of RAM for production use with 100+ users.  We **strongly
  recommend against installing with less than 2GB of RAM**, as you will
  likely experience OOM issues.  In the future we expect Zulip's RAM
  requirements to decrease to support smaller installations (see
  https://github.com/zulip/zulip/issues/32).
* At least 10GB of free disk for production use (more may be required
  if you intend to store uploaded files locally rather than in S3
  and your team uses that feature extensively)
* Outgoing HTTP(S) access to the public Internet.
* SSL Certificate for the host you're putting this on
  (e.g. zulip.example.com).  If you just want to see what
  Zulip looks like, we recommend installing the development
  environment detailed in README.md as that is easier to setup.
* Email credentials Zulip can use to send outgoing emails to users
  (e.g. email address confirmation emails during the signup process,
  missed message notifications, password reminders if you're not using
  SSO, etc.).


Installing Zulip in production
==============================

These instructions should be followed as root.

(1) Install the SSL certificates for your machine to
  `/etc/ssl/private/zulip.key` and `/etc/ssl/certs/zulip.combined-chain.crt`.

  If you don't know how to generate an SSL certificate, you can
  do the following to generate a self-signed certificate:

  ```
  apt-get install openssl
  openssl genrsa -des3 -passout pass:x -out server.pass.key 4096
  openssl rsa -passin pass:x -in server.pass.key -out zulip.key
  rm server.pass.key
  openssl req -new -key zulip.key -out server.csr
  openssl x509 -req -days 365 -in server.csr -signkey zulip.key -out zulip.combined-chain.crt
  rm server.csr
  cp zulip.key /etc/ssl/private/zulip.key
  cp zulip.combined-chain.crt /etc/ssl/certs/zulip.combined-chain.crt
  ```

  You will eventually want to get a properly signed SSL certificate
  (and note that at present the Zulip desktop app doesn't support
  self-signed certificates), but this will let you finish the
  installation process.  When you do get an actual certificate, you
  will need to install as /etc/ssl/certs/zulip.combined-chain.crt the
  full certificate authority chain, not just the certificate; see the
  section on "SSL certificate chains" [in the nginx
  docs](http://nginx.org/en/docs/http/configuring_https_servers.html)
  for how to do this:

  You can get a free, properly signed certificate from the [Let's
  Encrypt service](https://letsencrypt.org/); here are the simplified
  instructions for using it with Zulip (run it all as root):

  ```
  sudo apt-get install -y git bc openssl
  git clone https://github.com/letsencrypt/letsencrypt /opt/letsencrypt
  cd /opt/letsencrypt
  letsencrypt-auto certonly --standalone

  # Now symlink the certificates to make them available where Zulip expects them.
  ln -s /etc/letsencrypt/live/your_domain/privkey.pem /etc/ssl/private/zulip.key
  ln -s /etc/letsencrypt/live/your_domain/fullchain.pem /etc/ssl/certs/zulip.combined-chain.crt
  ```

  If you already had a webserver installed on the system (e.g. you
  previously installed Zulip and are now getting a cert), you will
  need to stop the webserver (e.g. `service nginx stop`) and start it
  again after (e.g. `service nginx start`) running the above.

  Finally, if you want to proceed with just an IP address, it is
  possible to finish a Zulip installation that way; just set
  EXTERNAL_HOST to be the IP address.

(2) Download [the latest built server tarball](https://www.zulip.com/dist/releases/zulip-server-latest.tar.gz)
  and unpack it to `/root/zulip`, e.g.
  ```
  wget https://www.zulip.com/dist/releases/zulip-server-latest.tar.gz
  mkdir -p /root/zulip && tar -xf zulip-server-latest.tar.gz --directory=/root/zulip --strip-components=1
  ```

(3) Run
  ```
  /root/zulip/scripts/setup/install
  ```
  This may take a while to run, since it will install a large number of
  packages via apt.

(4) Configure the Zulip server instance by filling in the settings in
  `/etc/zulip/settings.py`.  Be sure to fill in all the mandatory
  settings, enable at least one authentication mechanism, and do the
  configuration required for that authentication mechanism to work.
  See the section on "Authentication" below for more detail on
  configuring authentication mechanisms.

(5) Run
  ```
  su zulip -c /home/zulip/deployments/current/scripts/setup/initialize-database
  ```
  This will report an error if you did not fill in all the mandatory
  settings from `/etc/zulip/settings.py`.  Once this completes
  successfully, the main installation process will be complete, and if
  you are planning on using password authentication, you should be able
  to visit the URL for your server and register for an account.

(6) Subscribe to [the Zulip announcements Google Group](https://groups.google.com/forum/#!forum/zulip-announce)
  to get announcements about new releases, security issues, etc.


Authentication and logging into Zulip the first time
====================================================

(As you read and follow the instructions in this section, if you run
into trouble, check out the troubleshooting advice in the next major
section.)

Once you've finished installing Zulip, configuring your settings.py
file, and initializing the database, it's time to login to your new
installation.  By default, initialize-database creates 1 realm that
you can join, the `ADMIN_DOMAIN` realm (defined in
`/etc/zulip/settings.py`).

The `ADMIN_DOMAIN` realm is by default configured with the following settings:
* `restricted_to_domain=True`: Only people with emails ending with @ADMIN_DOMAIN can join.
* `invite_required=False`: An invitation is not required to join the realm.
* `invite_by_admin_only=False`: You don't need to be an admin user to invite other users.
* `mandatory_topics=False`: Users are not required to specify a topic when sending messages.

If you would like to change these settings, you can do so using the
Django management python shell (as the zulip user):

```
cd /home/zulip/deployments/current
./manage.py shell
from zerver.models import *
r = get_realm(settings.ADMIN_DOMAIN)
r.restricted_to_domain=False # Now anyone anywhere can login
r.save() # save to the database
```

If you realize you set `ADMIN_DOMAIN` wrong, in addition to fixing the
value in settings.py, you will also want to do a similar manage.py
process to set `r.domain = "newexample.com"`.  If you've already
changed `ADMIN_DOMAIN` in settings.py, you can use
`Realm.objects.all()` in the management shell to find the list of
realms and pass the domain of the realm that is not "zulip.com" to
`get_realm`.

Depending what authentication backend you're planning to use, you will
need to do some additional setup documented in the `settings.py` template:

* For Google authentication, you need to follow the configuration
  instructions around `GOOGLE_OAUTH2_CLIENT_ID` and `GOOGLE_CLIENT_ID`.

* For Email authentication, you will need to follow the configuration
  instructions for outgoing SMTP from Django.  You can use `manage.py
  send_test_email username@example.com` to test whether you've
  successfully configured outgoing SMTP.

You should be able to login now.  If you get an error, check
`/var/log/zulip/errors.log` for a traceback, and consult the next
section for advice on how to debug.  If you aren't able to figure it
out, email zulip-help@googlegroups.com with the traceback and we'll
try to help you out!

You will likely want to make your own user account an admin user,
which you can do via the following management command:

```
./manage.py knight username@example.com -f
```

Now that you are an administrator, you will have a special
"Administration" tab linked to from the upper-right gear menu in the
Zulip app that lets you deactivate other users, manage streams, change
the Realm settings you may have edited using manage.py shell above,
etc.

You can also use `manage.py knight` with the
`--permission=api_super_user` argument to create API super users,
which are needed to mirror messages to streams from other users for
the IRC and Jabber mirroring integrations (see
`bots/irc-mirror.py` and `bots/jabber_mirror.py` for some detail on these).

There are a large number of useful management commands under
`zerver/manangement/commands/`; you can also see them listed using
`./manage.py` with no arguments.

One such command worth highlighting because it's a valuable feature
with no UI in the Administration page is `./manage.py realm_filters`,
which allows you to configure certain patterns in messages to be
automatically linkified, e.g. whenever someone mentions "T1234" it
could be auto-linkified to ticket 1234 in your team's Trac instance.

Checking Zulip is healthy and debugging the services it depends on
==================================================================

You can check if the zulip application is running using:
```
supervisorctl status
```

And checking for errors in the Zulip errors logs under
`/var/log/zulip/`.  That contains one log file for each service, plus
`errors.log` (has all errors), `server.log` (logs from the Django and
Tornado servers), and `workers.log` (combined logs from the queue
workers).

After you change configuration in `/etc/zulip/settings.py` or fix a
misconfiguration, you will often want to restart the Zulip application.
You can restart Zulip using:

```
supervisorctl restart all
```

Similarly, you can stop Zulip using:

```
supervisorctl stop all
```

The Zulip application uses several major services to store and cache
data, queue messages, and otherwise support the Zulip application:

* postgresql
* rabbitmq-server
* nginx
* redis
* memcached

If one of these services is not installed or functioning correctly,
Zulip will not work.  Below we detail some common configuration
problems and how to resolve them:

* An AMQPConnectionError traceback or error running rabbitmqctl
  usually means that RabbitMQ is not running; to fix this, try:
  ```
  service rabbitmq-server restart
  ```
  If RabbitMQ fails to start, the problem is often that you are using
  a virtual machine with broken DNS configuration; you can often
  correct this by configuring `/etc/hosts` properly.

* If your browser reports no webserver is running, that is likely
  because nginx is not configured properly and thus failed to start.
  nginx will fail to start if you configured SSL incorrectly or did
  not provide SSL certificates.  To fix this, configure them properly
  and then run:
  ```
  service nginx restart
  ```

If you run into additional problems, [please report
them](https://github.com/zulip/zulip/issues) so that we can update
these lists!  The Zulip installation scripts logs its full output to
`/var/log/zulip/install.log`, so please include the context for any
tracebacks from that log.


Making your Zulip instance awesome
==================================

Once you've got Zulip setup, you'll likely want to configure it the
way you like.  There are four big things to focus on:

(1) Integrations.  We recommend setting up integrations for the major
tools that your team works with.  For example, if you're a software
development team, you may want to start with integrations for your
version control, issue tracker, CI system, and monitoring tools.

Spend time configuring these integrations to be how you like them --
if an integration is spammy, you may want to change it to not send
messages that nobody cares about (E.g. for the zulip.com trac
integration, some teams find they only want notifications when new
tickets are opened, commented on, or closed, and not every time
someone edits the metadata).

If Zulip doesn't have an integration you want, you can add your own!
Most integrations are very easy to write, and even more complex
integrations usually take less than a day's work to build.  We very
much appreciate contributions of new integrations; there is a brief
draft integration writing guide [here](https://github.com/zulip/zulip/issues/70).


It can often be valuable to integrate your own internal processes to
send notifications into Zulip; e.g. notifications of new customer
signups, new error reports, or daily reports on the team's key
metrics; this can often spawn discussions in response to the data.

(2) Streams and Topics.  If it feels like a stream has too much
traffic about a topic only of interest to some of the subscribers,
consider adding or renaming streams until you feel like your team is
working productively.

Second, most users are not used to topics.  It can require a bit of
time for everyone to get used to topics and start benefitting from
them, but usually once a team is using them well, everyone ends up
enthusiastic about how much topics make life easier.  Some tips on
using topics:

* When replying to an existing conversation thread, just click on the
  message, or navigate to it with the arrow keys and hit "r" or
  "enter" to reply on the same topic
* When you start a new conversation topic, even if it's related to the
  previous conversation, type a new topic in the compose box
* You can edit topics to fix a thread that's already been started,
  which can be helpful when onboarding new batches of users to the platform.

Third, setting default streams for new users is a great way to get
new users involved in conversations before they've accustomed
themselves with joining streams on their own. You can use the
[`set_default_streams`](https://github.com/zulip/zulip/blob/master/zerver/management/commands/set_default_streams.py)
command to set default streams for users within a realm:

```
python manage.py set_default_streams --domain=example.com --streams=foo,bar,...
```

(3) Notification settings.  Zulip gives you a great deal of control
over which messages trigger desktop notifications; you can configure
these extensively in the `/#settings` page (get there from the gear
menu).  If you find the desktop notifications annoying, consider
changing the settings to only trigger desktop notifications when you
receive a PM or are @-mentioned.

(4) The mobile and desktop apps.  Currently, the Zulip Desktop app
only supports talking to servers with a properly signed SSL
certificate, so you may find that you get a blank screen when you
connect to a Zulip server using a self-signed certificate.

The Zulip Android app in the Google Play store doesn't yet support
talking to non-zulip.com servers (and the iOS one doesn't support
Google auth SSO against non-zulip.com servers; there's a design for
how to fix that which wouldn't be a ton of work to implement).  If you
are interested in helping out with the Zulip mobile apps, shoot an
email to zulip-devel@googlegroups.com and the maintainers can guide
you on how to help.

For announcements about improvements to the apps, make sure to join
the zulip-announce@googlegroups.com list so that you can receive the
announcements when these become available.

(5) All the other features: Hotkeys, emoji, search filters,
@-mentions, etc.  Zulip has lots of great features, make sure your
team knows they exist and how to use them effectively.

(6) Enjoy your Zulip installation!  If you discover things that you
wish had been documented, please contribute documentation suggestions
either via a GitHub issue or pull request; we love even small
contributions, and we'd love to make the Zulip documentation cover
everything anyone might want to know about running Zulip in
production.


Maintaining and upgrading Zulip in production
=============================================

We recommend reading this entire section before doing your first
upgrade.

* To upgrade to a new version of the zulip server, download the
  appropriate release tarball from
  https://www.zulip.com/dist/releases/ and then run as root:
  ```
  /home/zulip/deployments/current/scripts/upgrade-zulip zulip-server-VERSION.tar.gz
  ```

  The upgrade process will shut down the service, run `apt-get
  upgrade`, a puppet apply, and any database migrations, and then
  bring the service back up.  This will result in some brief downtime
  for the service, which should be under 30 seconds unless there is an
  expensive transition involved.  Unless you have tested the upgrade
  in advance, we recommend doing upgrades at off hours.

  You can create your own release tarballs from a copy of zulip.git
  repository using `tools/build-release-tarball`.

* **Warning**: If you have modified configuration files installed by
  Zulip (e.g. the nginx configuration), the Zulip upgrade process will
  overwrite your configuration when it does the `puppet apply`.  You
  can test whether this will happen assuming no upstream changes to
  the configuration using `scripts/zulip-puppet-apply` (without the
  `-f` option), which will do a test puppet run and output and changes
  it would make.  Using this list, you can save a copy of any files
  that you've modified, do the upgrade, and then restore your
  configuration.  If you need to do this, please report the issue so
  that we can make the Zulip puppet configuration flexible enough to
  handle your setup.

* The Zulip upgrade script automatically logs output to
  /var/log/zulip/upgrade.log; please use those logs to include output
  that shows all errors in any bug reports.

* The Zulip upgrade process works by creating a new deployment under
  /home/zulip/deployments/ containing a complete copy of the Zulip
  server code, and then moving the symlinks at
  `/home/zulip/deployments/current` and `/root/zulip` as part of the
  upgrade process.  This means that if the new version isn't working,
  you can quickly downgrade to the old version by using
  `/home/zulip/deployments/<date>/scripts/restart-server` to return to
  a previous version that you've deployed (the version is specified
  via the path to the copy of `restart-server` you call).

* To update your settings, simply edit `/etc/zulip/settings.py` and then
  run `/home/zulip/deployments/current/scripts/restart-server` to
  restart the server

* You are responsible for running `apt-get upgrade` on your system on
  a regular basis to ensure that it is up to date with the latest
  security patches.

* To use the Zulip API with your Zulip server, you will need to use the
  API endpoint of e.g. `https://zulip.example.com/api`.  Our Python
  API example scripts support this via the
  `--site=https://zulip.example.com` argument.  The API bindings
  support it via putting `site=https://zulip.example.com` in your
  .zuliprc.

  Every Zulip integration supports this sort of argument (or e.g. a
  `ZULIP_SITE` variable in a zuliprc file or the environment), but this
  is not yet documented for some of the integrations (the included
  integration documentation on `/integrations` will properly document
  how to do this for most integrations).  Pull requests welcome to
  document this for those integrations that don't discuss this!

* Similarly, you will need to instruct your users to specify the URL
  for your Zulip server when using the Zulip desktop and mobile apps.

* As a measure to mitigate the impact of potential memory leaks in one
  of the Zulip daemons, the service automatically restarts itself
  every Sunday early morning.  See `/etc/cron.d/restart-zulip` for the
  precise configuration.

### Backups for Zulip

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

#### Restoration

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


#### Postgres streaming replication

Zulip has database configuration for using Postgres streaming
replication; you can see the configuration in these files:

* puppet/zulip_internal/manifests/postgres_slave.pp
* puppet/zulip_internal/manifests/postgres_master.pp
* puppet/zulip_internal/files/postgresql/*

Contribution of a step-by-step guide for setting this up (and moving
this configuration to be available in the main `puppet/zulip/` tree)
would be very welcome!


### Monitoring Zulip

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

### Scalability of Zulip

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

### Security Model

This section attempts to document the Zulip security model.  Since
this is new documentation, it likely does not cover every issue; if
there are details you're curious about, please feel free to ask
questions on the Zulip development mailing list (or if you think
you've found a security bug, please report it to support@zulip.com so
we can do a responsible security announcement).

#### Secure your Zulip server like your email server

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

#### Encryption and Authentication

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

#### Messages and History

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

#### Users and Bots

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

#### User-uploaded content

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

#### Final notes and security response

If you find some aspect of Zulip that seems inconsistent with this
security model, please report it to support@zulip.com so that we can
investigate and coordinate an appropriate security release if needed.

Zulip security announcements will be sent to
zulip-announce@googlegroups.com, so you should subscribe if you are
running Zulip in production.

Remote User SSO Authentication
==============================

Zulip supports integrating with a corporate Single-Sign-On solution.
There are a few ways to do it, but this section documents how to
configure Zulip to use an SSO solution that best supports Apache and
will set the `REMOTE_USER` variable:

(0) Check that `/etc/zulip/settings.py` has
`zproject.backends.ZulipRemoteUserBackend` as the only enabled value
in the `AUTHENTICATION_BACKENDS` list, and that `SSO_APPEND_DOMAIN` is
correct set depending on whether your SSO system uses email addresses
or just usernames in `REMOTE_USER`.

Make sure that you've restarted the Zulip server since making this
configuration change.

(1) Edit `/etc/zulip/zulip.conf` and change the `puppet_classes` line to read:

```
puppet_classes = zulip::voyager, zulip::apache_sso
```

(2) As root, run `/home/zulip/deployments/current/scripts/zulip-puppet-apply`
to install our SSO integration.

(3) To configure our SSO integration, edit
`/etc/apache2/sites-available/zulip-sso.example` and fill in the
configuration required for your SSO service to set `REMOTE_USER` and
place your completed configuration file at `/etc/apache2/sites-available/zulip-sso`

(4) Run `a2ensite zulip-sso` to enable the Apache integration site.

Now you should be able to visit `https://zulip.example.com/` and
login via the SSO solution.


### Troubleshooting Remote User SSO

This system is a little finicky to networking setup (e.g. common
issues have to do with /etc/hosts not mapping settings.EXTERNAL_HOST
to the Apache listening on 127.0.0.1/localhost, for example).  It can
often help while debugging to temporarily change the Apache config in
/etc/apache2/sites-available/zulip-sso to listen on all interfaces
rather than just 127.0.0.1 as you debug this.  It can also be helpful
to change /etc/nginx/zulip-include/app.d/external-sso.conf to
proxy_pass to a more explicit URL possibly not over HTTPS when
debugging.  The following log files can be helpful when debugging this
setup:

* /var/log/zulip/{errors.log,server.log} (the usual places)
* /var/log/nginx/access.log (nginx access logs)
* /var/log/apache2/zulip_auth_access.log (you may want to change
  LogLevel to "debug" in the apache config file to make this more
  verbose)

Here's a summary of how the remote user SSO system works assuming
you're using HTTP basic auth; this summary should help with
understanding what's going on as you try to debug:

* Since you've configured /etc/zulip/settings.py to only define the
  zproject.backends.ZulipRemoteUserBackend, zproject/settings.py
  configures /accounts/login/sso as HOME_NOT_LOGGED_IN, which makes
  `https://zulip.example.com/` aka the homepage for the main Zulip
  Django app running behind nginx redirect to /accounts/login/sso if
  you're not logged in.

* nginx proxies requests to /accounts/login/sso/ to an Apache instance
  listening on localhost:8888 apache via the config in
  /etc/nginx/zulip-include/app.d/external-sso.conf (using the upstream
  localhost:8888 defined in /etc/nginx/zulip-include/upstreams).

* The Apache zulip-sso site which you've enabled listens on
  localhost:8888 and presents the htpasswd dialogue; you provide
  correct login information and the request reaches a second Zulip
  Django app instance that is running behind Apache with with
  REMOTE_USER set.  That request is served by
  `zerver.views.remote_user_sso`, which just checks the REMOTE_USER
  variable and either logs in (sets a cookie) or registers the new
  user (depending whether they have an account).

* After succeeding, that redirects the user back to / on port 443
  (hosted by nginx); the main Zulip Django app sees the cookie and
  proceeds to load the site homepage with them logged in (just as if
  they'd logged in normally via username/password).

Again, most issues with this setup tend to be subtle issues with the
hostname/DNS side of the configuration.  Suggestions for how to
improve this SSO setup documentation are very welcome!


Postgres database details
=========================

#### Remote Postgres database

This is a bit annoying to setup, but you can configure Zulip to use a
dedicated postgres server by setting the `REMOTE_POSTGRES_HOST`
variable in /etc/zulip/settings.py, and configuring Postgres
certificate authentication (see
http://www.postgresql.org/docs/9.1/static/ssl-tcp.html and
http://www.postgresql.org/docs/9.1/static/libpq-ssl.html for
documentation on how to set this up and deploy the certificates) to
make the DATABASES configuration in `zproject/settings.py` work (or
override that configuration).

If you want to use a remote Postgresql database, you should configure
the information about the connection with the server. You need a user
called "zulip" in your database server. You can configure these
options in /etc/zulip/settings.py:

* REMOTE_POSTGRES_HOST: Name or IP address of the remote host
* REMOTE_POSTGRES_SSLMODE: SSL Mode used to connect to the server, different options you can use are:
  * disable: I don't care about security, and I don't want to pay the overhead of encryption.
  * allow: I don't care about security, but I will pay the overhead of encryption if the server insists on it.
  * prefer: I don't care about encryption, but I wish to pay the overhead of encryption if the server supports it.
  * require: I want my data to be encrypted, and I accept the overhead. I trust that the network will make sure I always connect to the server I want.
  * verify-ca: I want my data encrypted, and I accept the overhead. I want to be sure that I connect to a server that I trust.
  * verify-full: I want my data encrypted, and I accept the overhead. I want to be sure that I connect to a server I trust, and that it's the one I specify.

Then you should specify the password of the user zulip for the database in /etc/zulip/zulip-secrets.conf:

```
postgres_password = xxxx
```

Finally, you can stop your database on the Zulip server via:

```
sudo service postgresql stop
sudo update-rc.d postgresql disable
```

In future versions of this feature, we'd like to implement and
document how to the remote postgres database server itself
automatically by using the Zulip install script with a different set
of puppet manifests than the all-in-one feature; if you're interested
in working on this, post to the Zulip development mailing list and we
can give you some tips.

#### Debugging postgres database issues

When debugging postgres issues, in addition to the standard `pg_top`
tool, often it can be useful to use this query:

```
SELECT procpid,waiting,query_start,current_query FROM pg_stat_activity ORDER BY procpid;
```

which shows the currently running backends and their activity. This is
similar to the pg_top output, with the added advantage of showing the
complete query, which can be valuable in debugging.

To stop a runaway query, you can run `SELECT pg_cancel_backend(pid
int)` or `SELECT pg_terminate_backend(pid int)` as the 'postgres'
user. The former cancels the backend's current query and the latter
terminates the backend process. They are implemented by sending SIGINT
and SIGTERM to the processes, respectively.  We recommend against
sending a Postgres process SIGKILL. Doing so will cause the database
to kill all current connections, roll back any pending transactions,
and enter recovery mode.

#### Stopping the Zulip postgres database

To start or stop postgres manually, use the pg_ctlcluster command:

```
pg_ctlcluster 9.1 [--force] main {start|stop|restart|reload}
```

By default, using stop uses "smart" mode, which waits for all clients
to disconnect before shutting down the database. This can take
prohibitively long. If you use the --force option with stop,
pg_ctlcluster will try to use the "fast" mode for shutting
down. "Fast" mode is described by the manpage thusly:

  With the --force option the "fast" mode is used which rolls back all
  active transactions, disconnects clients immediately and thus shuts
  down cleanly. If that does not work, shutdown is attempted again in
  "immediate" mode, which can leave the cluster in an inconsistent state
  and thus will lead to a recovery run at the next start. If this still
  does not help, the postmaster process is killed. Exits with 0 on
  success, with 2 if the server is not running, and with 1 on other
  failure conditions. This mode should only be used when the machine is
  about to be shut down.

Many database parameters can be adjusted while the database is
running. Just modify /etc/postgresql/9.1/main/postgresql.conf and
issue a reload. The logs will note the change.

#### Debugging issues starting postgres

pg_ctlcluster often doesn't give you any information on why the
database failed to start. It may tell you to check the logs, but you
won't find any information there. pg_ctlcluster runs the following
command underneath when it actually goes to start Postgres:

```
/usr/lib/postgresql/9.1/bin/pg_ctl start -D /var/lib/postgresql/9.1/main -s -o  '-c config_file="/etc/postgresql/9.1/main/postgresql.conf"'
```

Since pg_ctl doesn't redirect stdout or stderr, running the above can
give you better diagnostic information. However, you might want to
stop Postgres and restart it using pg_ctlcluster after you've debugged
with this approach, since it does bypass some of the work that
pg_ctlcluster does.


#### Postgres Vacuuming alerts

The `autovac_freeze` postgres alert from `check_postgres` is
particularly important.  This alert indicates that the age (in terms
of number of transactions) of the oldest transaction id (XID) is
getting close to the `autovacuum_freeze_max_age` setting.  When the
oldest XID hits that age, Postgres will force a VACUUM operation,
which can often lead to sudden downtime until the operation finishes.
If it did not do this and the age of the oldest XID reached 2 billion,
transaction id wraparound would occur and there would be data loss.
To clear the nagios alert, perform a `VACUUM` in each indicated
database as a database superuser (`postgres`).

See
http://www.postgresql.org/docs/9.1/static/routine-vacuuming.html#VACUUM-FOR-WRAPAROUND
for more details on postgres vacuuming.
