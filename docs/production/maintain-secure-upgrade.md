# Maintain, secure, and upgrade

This page covers topics that will help you maintain a healthy, up-to-date, and
secure Zulip installation, including:

- [Monitoring](#monitoring)
- [Scalability](#scalability)
- [Management commands](#management-commands)

You may also want to read this related content:

- [Security Model](../production/security-model.md)
- [Backups, export and import](../production/export-and-import.md)
- [Upgrade or modify Zulip](../production/upgrade-or-modify.md)

## Monitoring

The complete Nagios configuration (sans secret keys) used to
monitor zulip.com is available under `puppet/zulip_ops` in the
Zulip Git repository (those files are not installed in the release
tarballs).

The Nagios plugins used by that configuration are installed
automatically by the Zulip installation process in subdirectories
under `/usr/lib/nagios/plugins/`.  The following is a summary of the
various Nagios plugins included with Zulip and what they check:

Application server and queue worker monitoring:

* `check_send_receive_time` (sends a test message through the system
  between two bot users to check that end-to-end message sending works)

* `check_rabbitmq_consumers` and `check_rabbitmq_queues` (checks for
  rabbitmq being down or the queue workers being behind)

* `check_queue_worker_errors` (checks for errors reported by the queue
  workers)

* `check_worker_memory` (monitors for memory leaks in queue workers)

* `check_email_deliverer_backlog` and `check_email_deliverer_process`
  (monitors for whether scheduled outgoing emails are being sent)

Database monitoring:

* `check_postgres_replication_lag` (checks streaming replication is up
  to date).

* `check_postgres` (checks the health of the postgres database)

* `check_postgres_backup` (checks backups are up to date; see above)

* `check_fts_update_log` (monitors for whether full-text search updates
  are being processed)

Standard server monitoring:

* `check_website_response.sh` (standard HTTP check)

* `check_debian_packages` (checks apt repository is up to date)

**Note**: While most commands require no special permissions,
  `check_email_deliverer_backlog`, requires the `nagios` user to be in
  the `zulip` group, in order to access `SECRET_KEY` and thus run
  Zulip management commands.

If you're using these plugins, bug reports and pull requests to make
it easier to monitor Zulip and maintain it in production are
encouraged!

## Scalability

This section attempts to address the considerations involved with
running Zulip with larger teams (especially >1000 users).

* For an organization with 100+ users, it's important to have more
  than 4GB of RAM on the system.  Zulip will install on a system with
  2GB of RAM, but with less than 3.5GB of RAM, it will run its
  [queue processors](../subsystems/queuing.md) multithreaded to conserve memory;
  this creates a significant performance bottleneck.

* [chat.zulip.org](../contributing/chat-zulip-org.md), with thousands of user
  accounts and thousands of messages sent every week, has 8GB of RAM,
  4 cores, and 80GB of disk.  The CPUs are essentially always idle,
  but the 8GB of RAM is important.

* We recommend using a [remote postgres
  database](postgres.md) for isolation, though it is
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

* Zulip 2.0 and later supports running multiple Tornado servers
  sharded by realm/organization, which is how we scale Zulip Cloud.

* However, Zulip does not yet support dividing traffic for a single
  Zulip realm between multiple application servers.  There are two
  issues: you need to share the memcached/Redis/RabbitMQ instance
  (these should can be moved to a network service shared by multiple
  servers with a bit of configuration) and the Tornado event system
  for pushing to browsers currently has no mechanism for multiple
  frontend servers (or event processes) talking to each other.  One
  can probably get a factor of 10 in a single server's scalability by
  [supporting multiple tornado processes on a single server](https://github.com/zulip/zulip/issues/372),
  which is also likely the first part of any project to support
  exchanging events amongst multiple servers.  The work for changing
  this is pretty far along, though, and thus while not generally
  available yet, we can set it up for users with an enterprise support
  contract.

Questions, concerns, and bug reports about this area of Zulip are very
welcome!  This is an area we are hoping to improve.

## Sections that have moved

These were once subsections of this page, but have since moved to
dedicated pages; we preserve them here to avoid breaking old links.

### Securing your Zulip server

Moved to [Security Model](../production/security-model.md).

### Upgrading

Moved to [Upgrading to a release](../production/upgrade-or-modify.html#upgrading-to-a-release).

### Upgrading from a Git repository

Moved to [Upgrading from a Git
repository](../production/upgrade-or-modify.html#upgrading-from-a-git-repository).

### Upgrading the operating system

Moved to [Upgrading the operating
system](../production/upgrade-or-modify.html#upgrading-the-operating-system).

## API and your Zulip URL

To use the Zulip API with your Zulip server, you will need to use the
API endpoint of e.g. `https://zulip.example.com/api`.  Our Python
API example scripts support this via the
`--site=https://zulip.example.com` argument.  The API bindings
support it via putting `site=https://zulip.example.com` in your
.zuliprc.

Every Zulip integration supports this sort of argument (or e.g. a
`ZULIP_SITE` variable in a zuliprc file or the environment), but this
is not yet documented for some of the integrations (the included
integration documentation on `/integrations` will properly document
how to do this for most integrations).  We welcome pull requests for
integrations that don't discuss this!

Similarly, you will need to instruct your users to specify the URL
for your Zulip server when using the Zulip desktop and mobile apps.

## Memory leak mitigation

As a measure to mitigate the impact of potential memory leaks in one
of the Zulip daemons, the service automatically restarts itself
every Sunday early morning.  See `/etc/cron.d/restart-zulip` for the
precise configuration.

## Management commands

Zulip has a large library of [Django management
commands](https://docs.djangoproject.com/en/1.8/ref/django-admin/#django-admin-and-manage-py).
To use them, you will want to be logged in as the `zulip` user and for
the purposes of this documentation, we assume the current working
directory is `/home/zulip/deployments/current`.

Below, we show several useful examples, but there are more than 100
in total.  We recommend skimming the usage docs (or if there are none,
the code) of a management command before using it, since they are
generally less polished and more designed for expert use than the rest
of the Zulip system.

### Running management commands

Many management commands require the Zulip realm/organization to
interact with as an argument, which you can specify via numeric or
string ID.

You can see all the organizations on your Zulip server using
`./manage.py list_realms`.

```
zulip@zulip:~$ /home/zulip/deployments/current/manage.py list_realms
id    string_id                                name
--    ---------                                ----
1     zulipinternal                            None
2                                              Zulip Community
```

(Note that every Zulip server has a special `zulipinternal` realm containing
system-internal bots like `welcome-bot`; you are unlikely to need to
interact with that realm.)

Unless you are
[hosting multiple organizations on your Zulip server](../production/multiple-organizations.md),
your single Zulip organization on the root domain will have the empty
string (`''`) as its `string_id`.  So you can run e.g.:
```
zulip@zulip:~$ /home/zulip/deployments/current/manage.py show_admins -r ''
```

Otherwise, the `string_id` will correspond to the organization's
subdomain.  E.g. on `it.zulip.example.com`, use
`/home/zulip/deployments/current/manage.py show_admins -r it`.

### manage.py shell

You can get an iPython shell with full access to code within the Zulip
project using `manage.py shell`, e.g., you can do the following to
change a user's email address:

```
$ /home/zulip/deployments/current/manage.py shell
In [1]: user_profile = get_user_profile_by_email("email@example.com")
In [2]: do_change_user_delivery_email(user_profile, "new_email@example.com")
```

#### manage.py dbshell

This will start a postgres shell connected to the Zulip database.

### Grant administrator access

You can make any user a realm administrator on the command line with
the `knight` management command:

```
./manage.py knight username@example.com -f
```

#### Creating API super users with manage.py

If you need to manage the IRC, Jabber, or Zephyr mirrors, you will
need to create API super users.  To do this, use `./manage.py knight`
with the `--permission=api_super_user` argument.  See the respective
integration scripts for these mirrors (under
[`zulip/integrations/`][integrations-source] in the [Zulip Python API
repo][python-api-repo]) for further detail on these.

[integrations-source]: https://github.com/zulip/python-zulip-api/tree/master/zulip/integrations
[python-api-repo]: https://github.com/zulip/python-zulip-api

#### Exporting users and realms with manage.py export

If you need to do an export of a single user or of an entire realm, we
have tools in `management/` that essentially export Zulip data to the
file system.

`export_single_user.py` exports the message history and realm-public
metadata for a single Zulip user (including that user's *received*
messages as well as their sent messages).

A good overview of the process for exporting a single realm when
moving a realm to a new server (without moving a full database dump)
is in
[management/export.py](https://github.com/zulip/zulip/blob/master/zerver/management/commands/export.py). We
recommend you read the comment there for words of wisdom on speed,
what is and is not exported, what will break upon a move to a new
server, and suggested procedure.

### Other useful manage.py commands

There are a large number of useful management commands under
`zerver/management/commands/`; you can also see them listed using
`./manage.py` with no arguments.

## Hosting multiple Zulip organizations

This is explained in detail on [its own page](../production/multiple-organizations.md).
