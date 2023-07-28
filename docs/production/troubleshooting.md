# Troubleshooting and monitoring

This page offers detailed guidance for troubleshooting and monitoring your Zulip
installation. If you suspect that you have encountered a bug, or are otherwise
unable to resolve an issue with your Zulip installation, best-effort community
support is available in the [Zulip development community ][chat-zulip-org]. We
provide free, interactive support for the vast majority of questions about
running a Zulip server.

To report a problem or ask a question, please start a new topic in the
[#production help][production-help] stream in the [Zulip development community
][chat-zulip-org]:

- Describe what you are trying to do and any problems you've encountered.
- Provide the relevant logs, such as the full traceback from the bottom
  of `/var/log/zulip/errors.log`, or the installation script logs at
  `/var/log/zulip/install.log`. Please post logging output using [code
  blocks][code-block], not screenshots.
- Be sure to include what version of Zulip Server you are running, or between
  which versions you are upgrading.

[chat-zulip-org]: https://zulip.com/development-community/
[production-help]: https://chat.zulip.org/#narrow/stream/31-production-help
[code-block]: https://zulip.com/help/code-blocks

Contact [sales@zulip.com](mailto:sales@zulip.com) if you'd like to
learn about paid support options, including phone support from Zulip's
core engineering team.

## Overview and resources

If you encounter issues while self-hosting Zulip, the first thing to
do is look at Zulip's logs, which are located in `/var/log/zulip/`.

That directory contains one log file for each service, plus
`errors.log` (has all errors and the first place you should check),
`server.log` (has logs from the Django and Tornado servers), and
`workers.log` (has combined logs from the queue workers). Zulip also
provides a [tool to search through `server.log`][log-search].

Zulip uses [Supervisor](http://supervisord.org/index.html) to monitor
and control its many Python services. Read the next section, [Using
supervisorctl](#using-supervisorctl), to learn how to use the
Supervisor client to monitor and manage services.

If you haven't already, now might be a good time to read Zulip's [architectural
overview](../overview/architecture-overview.md), particularly the
[Components](../overview/architecture-overview.md#components) section. This will help you
understand the many services Zulip uses.

The section [troubleshooting services](#troubleshooting-services)
on this page includes details about how to fix common issues with Zulip services.

[log-search]: ../subsystems/logging.md#searching-backend-log-files

## Using supervisorctl

To see what Zulip-related services are configured to
use Supervisor, look at `/etc/supervisor/conf.d/zulip.conf` and
`/etc/supervisor/conf.d/zulip-db.conf`.

Use the supervisor client `supervisorctl` to list the status of, stop, start,
and restart various services.

### Checking status with `supervisorctl status`

You can check if the Zulip application is running using:

```bash
supervisorctl status
```

When everything is running as expected, you will see something like this:

```console
process-fts-updates                                             RUNNING   pid 11392, uptime 19:40:06
smokescreen                                                     RUNNING   pid 3113, uptime 29 days, 21:58:32
zulip-django                                                    RUNNING   pid 11441, uptime 19:39:57
zulip-tornado                                                   RUNNING   pid 11397, uptime 19:40:03
zulip_deliver_scheduled_emails                                  RUNNING   pid 10289, uptime 19:41:04
zulip_deliver_scheduled_messages                                RUNNING   pid 10294, uptime 19:41:02
zulip-workers:zulip_events_deferred_work                        RUNNING   pid 10314, uptime 19:41:00
zulip-workers:zulip_events_digest_emails                        RUNNING   pid 10339, uptime 19:40:57
zulip-workers:zulip_events_email_mirror                         RUNNING   pid 10751, uptime 19:40:52
zulip-workers:zulip_events_email_senders                        RUNNING   pid 10769, uptime 19:40:49
zulip-workers:zulip_events_embed_links                          RUNNING   pid 11035, uptime 19:40:46
zulip-workers:zulip_events_embedded_bots                        RUNNING   pid 11139, uptime 19:40:43
zulip-workers:zulip_events_invites                              RUNNING   pid 11261, uptime 19:40:36
zulip-workers:zulip_events_missedmessage_emails                 RUNNING   pid 11346, uptime 19:40:21
zulip-workers:zulip_events_missedmessage_mobile_notifications   RUNNING   pid 11351, uptime 19:40:19
zulip-workers:zulip_events_outgoing_webhooks                    RUNNING   pid 11358, uptime 19:40:17
zulip-workers:zulip_events_user_activity                        RUNNING   pid 11365, uptime 19:40:14
zulip-workers:zulip_events_user_activity_interval               RUNNING   pid 11376, uptime 19:40:11
zulip-workers:zulip_events_user_presence                        RUNNING   pid 11384, uptime 19:40:08
```

If you see any services showing a status other than `RUNNING`, or you
see an uptime under 5 seconds (which indicates it's crashing
immediately after startup and repeatedly restarting), that service
isn't running. If you don't see relevant logs in
`/var/log/zulip/errors.log`, check the log file declared via
`stdout_logfile` for that service's entry in
`/etc/supervisor/conf.d/zulip.conf` for details. Logs only make it to
`/var/log/zulip/errors.log` once a service has started fully.

### Restarting services with `supervisorctl restart`

After you change configuration in `/etc/zulip/settings.py` or fix a
misconfiguration, you will often want to restart the Zulip
application. In order to restart all of Zulip's services, you can use:

```bash
/home/zulip/deployments/current/scripts/restart-server
```

If you want to restart just one of them, you can use
`supervisorctl`:

```bash
# You can use this for any service found in `supervisorctl list`
supervisorctl restart zulip-django
```

:::{warning}
A configuration file might be used by multiple services, so generally
`scripts/restart-server` is the correct tool to use for reloading
purposes. Only use `supervisorctl restart` for an individual service
if you're confident that this specific service requires restarting.
In particular, it is not the right tool for applying settings changes
in `/etc/zulip/settings.py` and may cause inconsistent behavior.
:::

### Stopping services with `supervisorctl stop`

Similarly, while stopping all of Zulip is best done by running
`scripts/stop-server`, you can stop individual Zulip services using:

```bash
# You can use this for any service found in `supervisorctl list`
supervisorctl stop zulip-django
```

## Troubleshooting services

The Zulip application uses several major open source services to store
and cache data, queue messages, and otherwise support the Zulip
application:

- PostgreSQL
- RabbitMQ
- nginx
- Redis
- memcached

If one of these services is not installed or functioning correctly,
Zulip will not work. Below we detail some common configuration
problems and how to resolve them:

- If your browser reports no webserver is running, that is likely
  because nginx is not configured properly and thus failed to start.
  nginx will fail to start if you configured SSL incorrectly or did
  not provide SSL certificates. To fix this, configure them properly
  and then run:

  ```bash
  service nginx restart
  ```

- If your host is being port scanned by unauthorized users, you may see
  messages in `/var/log/zulip/server.log` like

  ```text
  2017-02-22 14:11:33,537 ERROR Invalid HTTP_HOST header: '10.2.3.4'. You may need to add u'10.2.3.4' to ALLOWED_HOSTS.
  ```

  Django uses the hostnames configured in `ALLOWED_HOSTS` to identify
  legitimate requests and block others. When an incoming request does
  not have the correct HTTP Host header, Django rejects it and logs the
  attempt. For more on this issue, see the [Django release notes on Host header
  poisoning](https://www.djangoproject.com/weblog/2013/feb/19/security/#s-issue-host-header-poisoning)

- An AMQPConnectionError traceback or error running rabbitmqctl
  usually means that RabbitMQ is not running; to fix this, try:
  ```bash
  service rabbitmq-server restart
  ```
  If RabbitMQ fails to start, the problem is often that you are using
  a virtual machine with broken DNS configuration; you can often
  correct this by configuring `/etc/hosts` properly.

### Restrict unattended upgrades

:::{important}
We recommend that you disable or limit Ubuntu's unattended-upgrades
to skip some server packages. With unattended upgrades enabled but
not limited, the moment a new PostgreSQL release is published, your
Zulip server will have its PostgreSQL server upgraded (and thus
restarted). If you do disable unattended-upgrades, do not forget to
regularly install apt upgrades manually!
:::

Restarting one of the system services that Zulip uses (PostgreSQL,
memcached, Redis, or RabbitMQ) will drop the connections that
Zulip processes have to the service, resulting in future operations on
those connections throwing errors.

Zulip is designed to recover from system service downtime by creating
new connections once the system service is back up, so the Zulip
outage will end once the system service finishes restarting. But
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
installing system package updates to PostgreSQL, memcached,
RabbitMQ, or Redis.

You can ensure that the `unattended-upgrades` package never upgrades
PostgreSQL, memcached, Redis, or RabbitMQ, by configuring in
`/etc/apt/apt.conf.d/50unattended-upgrades`:

```text
// Python regular expressions, matching packages to exclude from upgrading
Unattended-Upgrade::Package-Blacklist {
    "libc\d+";
    "memcached$";
    "nginx-full$";
    "postgresql-\d+$";
    "rabbitmq-server$";
    "redis-server$";
    "supervisor$";
};
```

## Monitoring

Chat is mission-critical to many organizations. This section contains
advice on monitoring your Zulip server to minimize downtime.

First, we should highlight that Zulip sends Django error emails to
`ZULIP_ADMINISTRATOR` for any backend exceptions. A properly
functioning Zulip server shouldn't send any such emails, so it's worth
reporting/investigating any that you do see.

Beyond that, the most important monitoring for a Zulip server is
standard stuff:

- Basic host health monitoring for issues running out of disk space,
  especially for the database and where uploads are stored.
- Service uptime and standard monitoring for the [services Zulip
  depends on](#troubleshooting-services). Most monitoring software
  has standard plugins for nginx, PostgreSQL, Redis, RabbitMQ,
  and memcached, and those will work well with Zulip.
- `supervisorctl status` showing all services `RUNNING`.
- Checking for processes being OOM killed.

Beyond that, Zulip ships a few application-specific end-to-end health
checks. The Nagios plugins `check_send_receive_time`,
`check_rabbitmq_queues`, and `check_rabbitmq_consumers` are generally
sufficient to point to the cause of any Zulip production issue. See
the next section for details.

### Nagios configuration

The complete Nagios configuration (sans secret keys) used to
monitor zulip.com is available under `puppet/zulip_ops` in the
Zulip Git repository (those files are not installed in the release
tarballs).

The Nagios plugins used by that configuration are installed
automatically by the Zulip installation process in subdirectories
under `/usr/lib/nagios/plugins/`. The following is a summary of the
useful Nagios plugins included with Zulip and what they check:

Application server and queue worker monitoring:

- `check_send_receive_time`: Sends a test message through the system
  between two bot users to check that end-to-end message sending
  works. An effective end-to-end check for Zulip's Django and Tornado
  systems being healthy.
- `check_rabbitmq_consumers` and `check_rabbitmq_queues`: Effective
  checks for Zulip's RabbitMQ-based queuing systems being healthy.
- `check_worker_memory`: Monitors for memory leaks in queue workers.

Database monitoring:

- `check_fts_update_log`: Checks whether full-text search updates are
  being processed properly or getting backlogged.
- `check_postgres`: General checks for database health.
- `check_postgresql_backup`: Checks status of PostgreSQL backups.
- `check_postgresql_replication_lag`: Checks whether PostgreSQL streaming
  replication is up to date.

Standard server monitoring:

- `check_debian_packages`: Checks whether the system is behind on
  `apt upgrade`.

If you're using these plugins, bug reports and pull requests to make
it easier to monitor Zulip and maintain it in production are
encouraged!

## Memory leak mitigation

As a measure to mitigate the potential impact of any future memory
leak bugs in one of the Zulip daemons, Zulip service automatically
restarts itself every Sunday early morning. See
`/etc/cron.d/restart-zulip` for the precise configuration.
