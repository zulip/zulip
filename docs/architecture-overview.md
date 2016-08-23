Zulip architectural overview
============================

Key Codebases
-------------

The core Zulip application is at
[<https://github.com/zulip/zulip>](https://github.com/zulip/zulip) and
is a web application written in Python 2.7 (soon to also support
Python 3) and using the Django framework. That codebase includes
server-side code and the web client, as well as Python API bindings
and most of our integrations with other services and applications (see
[the directory structure guide](directory-structure.html)).

We maintain several separate repositories for integrations and other
glue code: a [Hubot adapter](https://github.com/zulip/hubot-zulip);
integrations with
[Phabricator](https://github.com/zulip/phabricator-to-zulip),
[Jenkins](https://github.com/zulip/zulip-jenkins-plugin),
[Puppet](https://github.com/matthewbarr/puppet-zulip),
[Redmine](https://github.com/zulip/zulip-redmine-plugin), and
[Trello](https://github.com/zulip/trello-to-zulip); [node.js API
bindings](https://github.com/zulip/zulip-node); and our [full-text
search PostgreSQL extension](https://github.com/zulip/tsearch_extras).

Our mobile clients are separate code repositories:
[Android](https://github.com/zulip/zulip-android), [iOS
(stable)](https://github.com/zulip/zulip-ios), and [our experimental
React Native iOS app](https://github.com/zulip/zulip-mobile). Our
[legacy desktop application (implemented in
QT/WebKit)](https://github.com/zulip/zulip-desktop) and our new, alpha
[cross-platform desktop app (implemented in
Electron)](https://github.com/zulip/zulip-electron) are also separate
repositories.

We use [Transifex](https://www.transifex.com/zulip/zulip/) to do
translations.

In this overview we'll mainly discuss the core Zulip server and web
application.

Usage assumptions and concepts
------------------------------

Zulip is a real-time web-based chat application meant for companies and
similar groups ranging in size from a small team to more than a thousand
users. It features real-time notifications, message persistence and
search, public group conversations (*streams*), invite-only streams,
private one-on-one and group conversations, inline image previews, team
presence/buddy list, a rich API, Markdown message support, and numerous
integrations with other services. The maintainer team aims to support
users who connect to Zulip using dedicated iOS, Android, Linux, Windows,
and Mac OS X clients, as well as people using modern web browsers or
dedicated Zulip API clients.

A server can host multiple Zulip *realms* (organizations) at the same
domain, each of which is a private chamber with its own users,
streams, customizations, and so on. This means that one person might
be a user of multiple Zulip realms. The administrators of a realm can
choose whether to allow anyone to register an account and join, or
only allow people who have been invited, or restrict registrations to
members of particular groups (using email domain names or corporate
single-sign-on login for verification). For more on scalability and
security considerations, see [the security section of the production
maintenance
instructions](prod-maintain-secure-upgrade.html#security-model).

The default Zulip home screen is like a chronologically ordered inbox;
it displays messages, starting at the oldest message that the user
hasn't viewed yet (for more on that logic, see [the guide to the
pointer and unread counts](pointer.html)). The home screen displays
the most recent messages in all the streams a user has joined (except
for the streams they've muted), as well as private messages from other
users, in strict chronological order. A user can *narrow* to view only
the messages in a single stream, and can further narrow to focus on a
*topic* (thread) within that stream. Each narrow has its own URL.

Zulip's philosophy is to provide sensible defaults but give the user
fine-grained control over their incoming information flow; a user can
mute topics and streams, and can make fine-grained choices to reduce
real-time notifications they find irrelevant.

Components
----------

### Tornado and Django

We use both the [Tornado](http://www.tornadoweb.org) and
[Django](https://www.djangoproject.com/) Python web frameworks.

Django is the main web application server; Tornado runs the
server-to-client real-time push system. The app servers are configured
by the Supervisor configuration (which explains how to start the server
processes; see "Supervisor" below) and the nginx configuration (which
explains which HTTP requests get sent to which app server).

Tornado is an asynchronous server and is meant specifically to hold open
tens of thousands of long-lived (long-polling or websocket) connections
-- that is to say, routes that maintain a persistent connection from
every running client. For this reason, it's responsible for event
(message) delivery, but not much else. We try to avoid any blocking
calls in Tornado because we don't want to delay delivery to thousands of
other connections (as this would make Zulip very much not real-time).
For instance, we avoid doing cache or database queries inside the
Tornado code paths, since those blocking requests carry a very high
performance penalty for a single-threaded, asynchronous server.

The parts that are activated relatively rarely (e.g. when people type or
click on something) are processed by the Django application server. One
exception to this is that Zulip uses websockets through Tornado to
minimize latency on the code path for **sending** messages.

### nginx

nginx is the front-end web server to all Zulip traffic; it serves static
assets and proxies to Django and Tornado. It handles HTTP requests
according to the rules laid down in the many config files found in
`zulip/puppet/zulip/files/nginx/`.

`zulip/puppet/zulip/files/nginx/zulip-include-frontend/app` is the most
important of these files. It explains what happens when requests come in
from outside.

-   In production, all requests to URLs beginning with `/static/` are
    served from the corresponding files in `/home/zulip/prod-static/`,
    and the production build process (`tools/build-release-tarball`)
    compiles, minifies, and installs the static assets into the
    `prod-static/` tree form. In development, files are served directly
    from `/static/` in the git repository.
-   Requests to `/json/get_events`, `/api/v1/events`, and `/sockjs` are
    sent to the Tornado server. These are requests to the real-time push
    system, because the user's web browser sets up a long-lived TCP
    connection with Tornado to serve as [a channel for push
    notifications](https://en.wikipedia.org/wiki/Push_technology#Long_Polling).
    nginx gets the hostname for the Tornado server via
    `puppet/zulip/files/nginx/zulip-include-frontend/upstreams`.
-   Requests to all other paths are sent to the Django app via the UNIX
    socket `unix:/home/zulip/deployments/fastcgi-socket` (defined in
    `puppet/zulip/files/nginx/zulip-include-frontend/upstreams`). We use
    `zproject/wsgi.py` to implement FastCGI here (see
    `django.core.wsgi`).

### Supervisor

We use [supervisord](http://supervisord.org/) to start server processes,
restart them automatically if they crash, and direct logging.

The config file is
`zulip/puppet/zulip/files/supervisor/conf.d/zulip.conf`. This is where
Tornado and Django are set up, as well as a number of background
processes that process event queues. We use event queues for the kinds
of tasks that are best run in the background because they are
expensive (in terms of performance) and don't have to be synchronous
--- e.g., sending emails or updating analytics. Also see [the queuing
guide](queuing.html).

### memcached

memcached is used to cache database model objects. `zerver/lib/cache.py`
and `zerver/lib/cache_helpers.py` manage putting things into memcached,
and invalidating the cache when values change. The memcached
configuration is in `puppet/zulip/files/memcached.conf`.

### Redis

Redis is used for a few very short-term data stores, such as in the
basis of `zerver/lib/rate_limiter.py`, a per-user rate limiting scheme
[example](http://blog.domaintools.com/2013/04/rate-limiting-with-redis/)),
and the [email-to-Zulip
integration](https://zulipchat.com/integrations/#email).

Redis is configured in `zulip/puppet/zulip/files/redis` and it's a
pretty standard configuration except for the last line, which turns off
persistence:

    # Zulip-specific configuration: disable saving to disk.
    save ""

memcached was used first and then we added Redis specifically to
implement rate limiting. [We're discussing switching everything over to
Redis.](https://github.com/zulip/zulip/issues/16)

### RabbitMQ

RabbitMQ is a queueing system. Its config files live in
`zulip/puppet/zulip/files/rabbitmq`. Initial configuration happens in
`zulip/scripts/setup/configure-rabbitmq`.

We use RabbitMQ for queuing expensive work (e.g. sending emails
triggered by a message, push notifications, some analytics, etc.) that
require reliable delivery but which we don't want to do on the main
thread. It's also used for communication between the application server
and the Tornado push system.

Two simple wrappers around `pika` (the Python RabbitMQ client) are in
`zulip/server/lib/queue.py`. There's an asynchronous client for use in
Tornado and a more general client for use elsewhere.

`zerver/lib/event_queue.py` has helper functions for putting events into
one queue or another. Most of the processes started by Supervisor are
queue processors that continually pull things out of a RabbitMQ queue
and handle them.

Also see [the queuing guide](queuing.html).

### PostgreSQL

PostgreSQL (also known as Postgres) is the database that stores all
persistent data, that is, data that's expected to live beyond a user's
current session.

In production, Postgres is installed with a default configuration. The
directory that would contain configuration files
(`puppet/zulip/files/postgresql`) has only a utility script and a custom
list of stopwords used by a Postgresql extension.

In a development environment, configuration of that postgresql
extension is handled by `tools/postgres-init-dev-db` (invoked by
`tools/provision.py`).  That file also manages setting up the
development postgresql user.

`tools/provision.py` also invokes `tools/do-destroy-rebuild-database`
to create the actual database with its schema.

### Nagios

Nagios is an optional component used for notifications to the system
administrator, e.g., in case of outages.

`zulip/puppet/zulip/manifests/nagios.pp` installs Nagios plugins from
puppet/`zulip/files/nagios_plugins/`.

This component is intended to install Nagios plugins intended to be run
on a Nagios server; most of the Zulip Nagios plugins are intended to be
run on the Zulip servers themselves, and are included with the relevant
component of the Zulip server (e.g.
`puppet/zulip/manifests/postgres_common.pp` installs a few under
`/usr/lib/nagios/plugins/zulip_postgres_common`).
