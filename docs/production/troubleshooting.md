# Troubleshooting and monitoring

Zulip uses [Supervisor](http://supervisord.org/index.html) to monitor
and control its many Python services. Read the next section, [Using
supervisorctl](#using-supervisorctl), to learn how to use the
Supervisor client to monitor and manage services.

If you haven't already, now might be a good time to read Zulip's [architectural
overview](../overview/architecture-overview.md), particularly the
[Components](../overview/architecture-overview.html#components) section. This will help you
understand the many services Zulip uses.

If you encounter issues while running Zulip, take a look at Zulip's logs, which
are located in  `/var/log/zulip/`. That directory contains one log file for
each service, plus `errors.log` (has all errors), `server.log` (has logs from
the Django and Tornado servers), and `workers.log` (has combined logs from the
queue workers).

The section [troubleshooting services](#troubleshooting-services)
on this page includes details about how to fix common issues with Zulip services.

If you run into additional problems, [please report
them](https://github.com/zulip/zulip/issues) so that we can update
this page!  The Zulip installation scripts logs its full output to
`/var/log/zulip/install.log`, so please include the context for any
tracebacks from that log.

## Using supervisorctl

To see what Zulip-related services are configured to
use Supervisor, look at `/etc/supervisor/conf.d/zulip.conf` and
`/etc/supervisor/conf.d/zulip-db.conf`.

Use the supervisor client `supervisorctl` to list the status of, stop, start,
and restart various services.

### Checking status with `supervisorctl status`

You can check if the zulip application is running using:
```
supervisorctl status
```

When everything is running as expected, you will see something like this:

```
process-fts-updates                                             RUNNING   pid 2194, uptime 1:13:11
zulip-django                                                    RUNNING   pid 2192, uptime 1:13:11
zulip-tornado                                                   RUNNING   pid 2193, uptime 1:13:11
zulip-workers:zulip-events-confirmation-emails                  RUNNING   pid 2199, uptime 1:13:11
zulip-workers:zulip-events-digest_emails                        RUNNING   pid 2205, uptime 1:13:11
zulip-workers:zulip-events-email_mirror                         RUNNING   pid 2203, uptime 1:13:11
zulip-workers:zulip-events-error_reports                        RUNNING   pid 2200, uptime 1:13:11
zulip-workers:zulip-events-missedmessage_mobile_notifications   RUNNING   pid 2204, uptime 1:13:11
zulip-workers:zulip-events-missedmessage_reminders              RUNNING   pid 2206, uptime 1:13:11
zulip-workers:zulip-events-signups                              RUNNING   pid 2198, uptime 1:13:11
zulip-workers:zulip-events-slowqueries                          RUNNING   pid 2202, uptime 1:13:11
zulip-workers:zulip-events-user-activity                        RUNNING   pid 2197, uptime 1:13:11
zulip-workers:zulip-events-user-activity-interval               RUNNING   pid 2196, uptime 1:13:11
zulip-workers:zulip-events-user-presence                        RUNNING   pid 2195, uptime 1:13:11
```

If you see any services showing a status other than `RUNNING`, or you
see an uptime under 5 seconds (which indicates it's crashing
immediately after startup and repeatedly restarting), that service
isn't running.  If you don't see relevant logs in
`/var/log/zulip/errors.log`, check the log file declared via
`stdout_logfile` for that service's entry in
`/etc/supervisor/conf.d/zulip.conf` for details.  Logs only make it to
`/var/log/zulip/errors.log` once a service has started fully.

### Restarting services with `supervisorctl restart all`

After you change configuration in `/etc/zulip/settings.py` or fix a
misconfiguration, you will often want to restart the Zulip application.
You can restart Zulip using:

```
supervisorctl restart all
```

### Stopping services with `supervisorctl stop all`

Similarly, you can stop Zulip using:

```
supervisorctl stop all
```

## Troubleshooting services

The Zulip application uses several major open source services to store
and cache data, queue messages, and otherwise support the Zulip
application:

* postgresql
* rabbitmq-server
* nginx
* redis
* memcached

If one of these services is not installed or functioning correctly,
Zulip will not work.  Below we detail some common configuration
problems and how to resolve them:

* If your browser reports no webserver is running, that is likely
  because nginx is not configured properly and thus failed to start.
  nginx will fail to start if you configured SSL incorrectly or did
  not provide SSL certificates.  To fix this, configure them properly
  and then run:
  ```
  service nginx restart
  ```

* If your host is being port scanned by unauthorized users, you may see
  messages in `/var/log/zulip/server.log` like
  ```
  2017-02-22 14:11:33,537 ERROR Invalid HTTP_HOST header: '10.2.3.4'. You may need to add u'10.2.3.4' to ALLOWED_HOSTS.
  ```
  Django uses the hostnames configured in `ALLOWED_HOSTS` to identify
  legitimate requests and block others. When an incoming request does
  not have the correct HTTP Host header, Django rejects it and logs the
  attempt. For more on this issue, see the [Django release notes on Host header
  poisoning](https://www.djangoproject.com/weblog/2013/feb/19/security/#s-issue-host-header-poisoning)

* An AMQPConnectionError traceback or error running rabbitmqctl
  usually means that RabbitMQ is not running; to fix this, try:
  ```
  service rabbitmq-server restart
  ```
  If RabbitMQ fails to start, the problem is often that you are using
  a virtual machine with broken DNS configuration; you can often
  correct this by configuring `/etc/hosts` properly.

### Disabling unattended upgrades

```eval_rst
.. important::
    We recommend that you `disable Ubuntu's unattended-upgrades
    <https://linoxide.com/ubuntu-how-to/enable-disable-unattended-upgrades-ubuntu-16-04/>`_
    and instead install apt upgrades manually.  With unattended upgrades
    enabled, the moment a new Postgres release is published, your Zulip
    server will have its postgres server upgraded (and thus restarted).
```

Restarting one of the system services that Zulip uses (`postgres`,
`memcached`, `redis`, or `rabbitmq`) will drop the connections that
Zulip processes have to the service, resulting in future operations on
those connections throwing errors.

Zulip is designed to recover from system service downtime by creating
new connections once the system service is back up, so the Zulip
outage will end once the system service finishes restarting.  But
you'll get a bunch of error emails during the system service outage
whenever one of the Zulip server's ~20 workers attempts to access the
system service.

An unplanned outage will also result in an annoying (and potentially
confusing) trickle of error emails over the following hours or days.
These emails happen because a worker only learns its connection was
dropped when it next tries to access the connection (at which point
it'll send an error email and make a new connection), and several
workers are commonly idle for periods of hours or days at a time.

You can prevent this trickle when doing a planned upgrade by
restarting the Zulip server with
`/home/zulip/deployments/current/scripts/restart-server` after
installing system package updates to `postgres`, `memcached`,
`rabbitmq`, or `redis`.

Few system administrators enjoy outages at random times (even if only
brief) or the resulting distribution of error emails, which is why we
recommend disabling `unattended-upgrades`.

## Monitoring

Chat is mission-critical to many organizations.  This section contains
advice on monitoring your Zulip server to minimize downtime.

First, we should highlight that Zulip sends Django error emails to
`ZULIP_ADMINISTRATOR` for any backend exceptions.  A properly
functioning Zulip server shouldn't send any such emails, so it's worth
reporting/investigating any that you do see.

Beyond that, the most important monitoring for a Zulip server is
standard stuff:

* Basic host health monitoring for issues running out of disk space,
  especially for the database and where uploads are stored.
* Service uptime and standard monitoring for the [services Zulip
  depends on](#troubleshooting-services).  Most monitoring software
  has standard plugins for `nginx`, `postgres`, `redis`, `rabbitmq`,
  and `memcached`, and those will work well with Zulip.
* `supervisorctl status` showing all services `RUNNING`.
* Checking for processes being OOM killed.

Beyond that, Zulip ships a few application-specific end-to-end health
checks.  The Nagios plugins `check_send_receive_time`,
`check_rabbitmq_queues`, and `check_rabbitmq_consumers` are generally
sufficient to point to the cause of any Zulip production issue.  See
the next section for details.

### Nagios configuration

The complete Nagios configuration (sans secret keys) used to
monitor zulip.com is available under `puppet/zulip_ops` in the
Zulip Git repository (those files are not installed in the release
tarballs).

The Nagios plugins used by that configuration are installed
automatically by the Zulip installation process in subdirectories
under `/usr/lib/nagios/plugins/`.  The following is a summary of the
useful Nagios plugins included with Zulip and what they check:

Application server and queue worker monitoring:

* `check_send_receive_time`: Sends a test message through the system
  between two bot users to check that end-to-end message sending
  works.  An effective end-to-end check for Zulip's Django and Tornado
  systems being healthy.
* `check_rabbitmq_consumers` and `check_rabbitmq_queues`: Effective
  checks for Zulip's RabbitMQ-based queuing systems being healthy.
* `check_worker_memory`: Monitors for memory leaks in queue workers.
* `check_email_deliverer_backlog` and `check_email_deliverer_process`:
  Monitors for whether scheduled outgoing emails (e.g. invitation
  reminders) are being sent properly.

Database monitoring:

* `check_fts_update_log`: Checks whether full-text search updates are
  being processed properly or getting backlogged.
* `check_postgres`: General checks for database health.
* `check_postgres_backup`: Checks status of postgres backups.
* `check_postgres_replication_lag`: Checks whether postgres streaming
  replication is up to date.

Standard server monitoring:

* `check_website_response.sh`: Basic HTTP check.
* `check_debian_packages`: Checks whether the system is behind on `apt
  upgrade`.

If you're using these plugins, bug reports and pull requests to make
it easier to monitor Zulip and maintain it in production are
encouraged!

## Memory leak mitigation

As a measure to mitigate the potential impact of any future memory
leak bugs in one of the Zulip daemons, Zulip service automatically
restarts itself every Sunday early morning.  See
`/etc/cron.d/restart-zulip` for the precise configuration.
