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

Next: [Making your Zulip instance awesome.](prod-customize.html)
