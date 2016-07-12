Zulip in production
===================

This documents the process for installing Zulip in a production environment.

Note that if you just want to play around with Zulip and see what it
looks like, it is easier to install it in a development environment
following the instructions in README.dev, since then you don't need to
worry about setting up SSL certificates and an authentication mechanism.

## Requirements and recommendations

See [Requirements and recommendations for installing Zulip in
production](https://zulip.readthedocs.io/en/latest/prod-requirements.html).


Installing Zulip in production
==============================

See [Installing Zulip in production](https://zulip.readthedocs.io/en/latest/prod-install.html).


Authentication and logging into Zulip the first time
====================================================

See [Authentication and logging into Zulip the first time](https://zulip.readthedocs.io/en/latest/prod-auth-first-login.html).


Checking Zulip is healthy and debugging the services it depends on
==================================================================

See [Checking Zulip is healthy and debugging the services it depends on](https://zulip.readthedocs.io/en/latest/prod-health-check-debug.html).


Making your Zulip instance awesome
==================================

See [Making your Zulip instance
awesome](https://zulip.readthedocs.io/en/latest/prod-customize.html).


Maintaining and upgrading Zulip in production
=============================================

See [Maintaining and upgrading Zulip in production](https://zulip.readthedocs.io/en/latest/prod-maintain-secure-upgrade.html).


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
place your completed configuration file at `/etc/apache2/sites-available/zulip-sso.conf`

`zulip-sso.example` is correct configuration for using an `htpasswd`
file for `REMOTE_USER` authentication, which is useful for testing
quickly.  You can set it up by doing the following:

```
/home/zulip/deployments/current/scripts/restart-server
cd /etc/apache2/sites-available/
cp zulip-sso.example zulip-sso.conf
htpasswd -c /home/zulip/zpasswd username@example.com # prompts for a password
```

and then continuing with the steps below.

(4) Run `a2ensite zulip-sso` to enable the Apache integration site.

(5) Run `service apache2 reload` to use your new configuration.  If
Apache isn't already running, you may need to run `service apache2
start` instead.

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
