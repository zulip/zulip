Zulip in production
===================

This documents the process for installing Zulip in a production environment.

Note that if you just want to play around with Zulip and see what it
looks like, it is easier to install it in a development environment
following the instructions in README.dev, since then you don't need to
worry about setting up SSL certificates and an authentication mechanism.

Recommended requirements:

* Server running Ubuntu Precise or Debian Wheezy
* At least 2 CPUs for production use with 100+ users
* At least 4GB of RAM for production use with 100+ users.  We strongly
  recommend against installing with less than 2GB of RAM, as you will
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
    `/etc/ssl/private/zulip.key` and `/etc/ssl/certs/zulip.combined-chain.crt`

(2) Download `zulip-server.tar.gz`, and unpack to it `/root/zulip`, e.g.
    ```
    tar -xf zulip-server-1.1.3.tar.gz
    mv zulip-server-1.1.3 /root/zulip
    ```

(3) run
    ```/root/zulip/scripts/setup/install```
    This may take a while to run, since it will install a large number of
    packages via apt.

(4) Configure the Zulip server instance by filling in the settings in
    `/etc/zulip/settings.py`.

(6) Run
```su zulip -c /home/zulip/deployments/current/scripts/setup/initialize-database```
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
following process as the zulip user:

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
process to set `r.domain = newexample.com`.

Depending what authentication backend you're planning to use, you will
need to do some additional setup documented in the `settings.py` template:

* For Google authentication, you need to follow the configuration
  instructions around `GOOGLE_OAUTH2_CLIENT_ID` and `GOOGLE_CLIENT_ID`.
* For Email authentication, you will need to follow the configuration
  instructions around outgoing SMTP from Django.

You should be able to login now.  If you get an error, check
`/var/log/zulip/errors.log` for a traceback, and consult the next
section for advice on how to debug.  If you aren't able to figure it
out, email zulip-devel@googlegroups.com with the traceback and we'll
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

If you run into additional problems, [please report them](https://github.com/zulip/zulip/issues) so that we can
update these lists!


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

The Zulip iOS and Android apps in their respective stores don't yet
support talking to non-zulip.com servers; the iOS app is waiting on
Apple's app store review, while the Android app is waiting on someone
to do the small project of adding a field to specify what Zulip server
to talk to.

These issues will likely all be addressed in the coming weeks; make
sure to join the zulip-announce@googlegroups.com list so that you can
receive the announcements when these become available.

(5) All the other features: Hotkeys, emoji, search filters,
@-mentions, etc.  Zulip has lots of great features, make sure your
team knows they exist and how to use them effectively.

(6) Enjoy your Zulip installation!  If you discover things that you
wish had been documented, please contribute documentation suggestions
either via a GitHub issue or pull request; we love even small
contributions, and we'd love to make the Zulip documentation cover
everything anyone might want to know about running Zulip in
production.


Maintaining Zulip in production
===============================

* To upgrade to a new version, download the appropriate release
  tarball from https://www.zulip.org, and then run as root

  ```
  /home/zulip/deployments/current/scripts/upgrade-zulip <tarball>
  ```

  The upgrade process will shut down the service, run `apt-get
  upgrade` and any database migrations, and then bring the service
  back up.  This will result in some brief downtime for the service,
  which should be under 30 seconds unless there is an expensive
  transition involved.  Unless you have tested the upgrade in advance,
  we recommend doing upgrades at off hours.

  You can create your own release tarballs from a copy of zulip.git
  repository using `tools/build-release-tarball`.

* To update your settings, simply edit `/etc/zulip/settings.py` and then
  run `/home/zulip/deployments/current/scripts/restart-server` to
  restart the server

* You are responsible for running `apt-get upgrade` on your system on
  a regular basis to ensure that it is up to date with the latest
  security patches.

* To use the Zulip API with your Zulip server, you will need to use the
  API endpoint of e.g. `https://zulip.yourdomain.net/api`.  Our Python
  API example scripts support this via the
  `--site=https://zulip.yourdomain.net` argument.  The API bindings
  support it via putting `site=https://zulip.yourdomain.net` in your
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


SSO Authentication
==================

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
puppet_classes = zulip::enterprise, zulip::apache_sso
```

(2) As root, run `/home/zulip/deployments/current/scripts/zulip-puppet-apply`
to install our SSO integration.

(3) To configure our SSO integration, edit
`/etc/apache2/sites-available/zulip-sso.example` and fill in the
configuration required for your SSO service to set `REMOTE_USER` and
place your completed configuration file at `/etc/apache2/sites-available/zulip-sso`

(4) Run `a2ensite zulip-sso` to enable the Apache integration site.

Now you should be able to visit `https://zulip.yourdomain.net/` and
login via the SSO solution.
