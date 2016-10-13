# Troubleshooting

Zulip uses [Supervisor](http://supervisord.org/index.html) to monitor
and control its many Python services. Read the next section, [Using
supervisorctl](#using-supervisorctl), to learn how to use the
Supervisor client to monitor and manage services.

If you haven't already, now might be a good time to read Zulip's [architectural
overview](architecture-overview.html), particularly the
[Components](architecture-overview.html#components) section. This will help you
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
zulip-senders:zulip-events-message_sender-0                     RUNNING   pid 2209, uptime 1:13:11
zulip-senders:zulip-events-message_sender-1                     RUNNING   pid 2210, uptime 1:13:11
zulip-senders:zulip-events-message_sender-2                     RUNNING   pid 2211, uptime 1:13:11
zulip-senders:zulip-events-message_sender-3                     RUNNING   pid 2212, uptime 1:13:11
zulip-senders:zulip-events-message_sender-4                     RUNNING   pid 2208, uptime 1:13:11
zulip-tornado                                                   RUNNING   pid 2193, uptime 1:13:11
zulip-workers:zulip-deliver-enqueued-emails                     STARTING
zulip-workers:zulip-events-confirmation-emails                  RUNNING   pid 2199, uptime 1:13:11
zulip-workers:zulip-events-digest_emails                        RUNNING   pid 2205, uptime 1:13:11
zulip-workers:zulip-events-email_mirror                         RUNNING   pid 2203, uptime 1:13:11
zulip-workers:zulip-events-error_reports                        RUNNING   pid 2200, uptime 1:13:11
zulip-workers:zulip-events-feedback_messages                    RUNNING   pid 2207, uptime 1:13:11
zulip-workers:zulip-events-missedmessage_mobile_notifications   RUNNING   pid 2204, uptime 1:13:11
zulip-workers:zulip-events-missedmessage_reminders              RUNNING   pid 2206, uptime 1:13:11
zulip-workers:zulip-events-signups                              RUNNING   pid 2198, uptime 1:13:11
zulip-workers:zulip-events-slowqueries                          RUNNING   pid 2202, uptime 1:13:11
zulip-workers:zulip-events-user-activity                        RUNNING   pid 2197, uptime 1:13:11
zulip-workers:zulip-events-user-activity-interval               RUNNING   pid 2196, uptime 1:13:11
zulip-workers:zulip-events-user-presence                        RUNNING   pid 2195, uptime 1:13:11
```

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

Next: [Making your Zulip instance awesome.](prod-customize.html)
