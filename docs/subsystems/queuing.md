# Queue processors

Zulip uses RabbitMQ to manage a system of internal queues. These are
used for a variety of purposes:

- Asynchronously doing expensive operations like sending email
  notifications which can take seconds per email and thus would
  otherwise time out when 100s are triggered at once (E.g. inviting a
  lot of new users to a realm).

- Asynchronously doing non-time-critical somewhat expensive operations
  like updating analytics tables (e.g. UserActivityInternal) which
  don't have any immediate runtime effect.

- Communicating events to push to clients (browsers, etc.) from the
  main Zulip Django application process to the Tornado-based events
  system. Example events might be that a new message was sent, a user
  has changed their subscriptions, etc.

- Processing mobile push notifications and email mirroring system
  messages.

- Processing various errors, frontend tracebacks, and slow database
  queries in a batched fashion.

Needless to say, the RabbitMQ-based queuing system is an important
part of the overall Zulip architecture, since it's in critical code
paths for everything from signing up for account, to rendering
messages, to delivering updates to clients.

We use the `pika` library to interface with RabbitMQ, using a simple
custom integration defined in `zerver/lib/queue.py`.

### Adding a new queue processor

To add a new queue processor:

- Define the processor in `zerver/worker/` using the `@assign_queue` decorator;
  it's pretty easy to get the template for an existing similar queue
  processor. This suffices to test your queue worker in the Zulip development
  environment (`tools/run-dev` will automatically restart the queue processors
  and start running your new queue processor code). You can also run a single
  queue processor manually using e.g. `./manage.py process_queue --queue=user_activity`.

- So that supervisord will know to run the queue processor in
  production, you will need to add to the `queues` variable in
  `puppet/zulip/manifests/app_frontend_base.pp`; the list there is
  used to generate `/etc/supervisor/conf.d/zulip.conf`.

The queue will automatically be added to the list of queues tracked by
`scripts/nagios/check-rabbitmq-consumers`, so Nagios can properly
check whether a queue processor is running for your queue. You still
need to update the sample Nagios configuration in `puppet/kandra`
manually.

### Publishing events into a queue

You can publish events to a RabbitMQ queue using the
`queue_json_publish` function defined in `zerver/lib/queue.py`.

An interesting challenge with queue processors is what should happen
when queued events in Zulip's backend tests. Our current solution is
that in the tests, `queue_json_publish` will (by default) simple call
the `consume` method for the relevant queue processor. However,
`queue_json_publish` also supports being passed a function that should
be called in the tests instead of the queue processor's `consume`
method. Where possible, we prefer the model of calling `consume` in
tests since that's more predictable and automatically covers the queue
processor's code path, but it isn't always possible.

### Clearing a RabbitMQ queue

If you need to clear a queue (delete all the events in it), run
`./manage.py purge_queue <queue_name>`, for example:

```bash
./manage.py purge_queue user_activity
```

You can also use the amqp tools directly. Install `amqp-tools` from
apt and then run:

```bash
amqp-delete-queue --username=zulip --password='...' --server=localhost \
   --queue=user_presence
```

with the RabbitMQ password from `/etc/zulip/zulip-secrets.conf`.
