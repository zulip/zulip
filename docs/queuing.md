# Queue processors

Zulip uses RabbitMQ to manage a system of internal queues.  These are
used for a variety of purposes:

* Asynchronously doing expensive operations like sending email
  notifications which can take seconds per email and thus would
  otherwise timeout when 100s are triggered at once (E.g. inviting a
  lot of new users to a realm).

* Asynchronously doing non-time-critical somewhat expensive operations
  like updating analytics tables (e.g. UserActivityInternal) which
  don't have any immediate runtime effect.

* Communicating events to push to clients (browsers, etc.) from the
  main Zulip Django application process to the Tornado-based events
  system.  Example events might be that a new message was sent, a user
  has changed their subscriptions, etc.

* Processing mobile push notifications and email mirroring system
  messages.

* Processing various errors, frontend tracebacks, and slow database
  queries in a batched fashion.

* Doing markdown rendering for messages delivered to the Tornado via
  websockets.

Needless to say, the RabbitMQ-based queuing system is an important
part of the overall Zulip architecture, since it's in critical code
paths for everything from signing up for account, to rendering
messages, to delivering updates to clients.

We use the `pika` library to interface with RabbitMQ, using a simple
custom integration defined in `zerver/lib/queue.py`.

### Adding a new queue processor

To add a new queue processor:

* Define the processor in `zerver/worker/queue_processors.py` using
  the `@assign_queue` decorator; it's pretty easy to get the template
  for an existing similar queue processor.  This suffices to test your
  queue worker in the Zulip development environment
  (`tools/run-dev.py` will automatically restart the queue processors
  and start running your new queue processor code).  You can also run
  a single queue processor manually using e.g. `./manage.py
  process_queue --queue=user_activity`.

* So that supervisord will known to run the queue processor in
  production, you will need to define a program entry for it in
  `servers/puppet/modules/zulip/files/supervisor/conf.d/zulip.conf`
  and add it to the `zulip-workers` group further down in the file.

* For monitoring, you need to add a check that your worker is running
  to puppet/zulip/files/cron.d/rabbitmq-numconsumers if it's a
  one-at-a-time consumer like `user_activity_internal` or a custom
  nagios check if it is a bulk processor like `slow_queries`.

### Publishing events into a queue

You can publish events to a RabbitMQ queue using the
`queue_json_publish` function defined in `zerver/lib/queue.py`.

### Clearing a RabbitMQ queue

If you need to clear a queue (delete all the events in it), run
`./manage.py purge_queue <queue_name>`, for example:

```
./manage.py purge_queue user_activity
```

You can also use the amqp tools directly.  Install `amqp-tools` from
apt and then run:

```
amqp-delete-queue --username=zulip --password='...' --server=localhost \
   --queue=user_presence
```

with the RabbitMQ password from `/etc/zulip/zulip-secrets.conf`.
