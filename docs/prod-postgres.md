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
