Zulip architectural overview
============================

Key Codebases
-------------

The core Zulip application is at
[<https://github.com/zulip/zulip>](https://github.com/zulip/zulip) and
is a web application written in Python 3.x and using the Django framework. That
codebase includes server-side code and the web client, as well as Python API
bindings and most of our integrations with other services and applications (see
[the directory structure guide](../overview/directory-structure.html)).

[Zulip Mobile](https://github.com/zulip/zulip-mobile) is the official
mobile Zulip client supporting both iOS and Android, written in
JavaScript with React Native, and
[Zulip Desktop](https://github.com/zulip/zulip-electron) is the
official Zulip desktop client for macOS, Linux, and Windows.

We also maintain several separate repositories for integrations and
other glue code: a
[Hubot adapter](https://github.com/zulip/hubot-zulip); integrations
with [Phabricator](https://github.com/zulip/phabricator-to-zulip),
[Jenkins](https://github.com/zulip/zulip-jenkins-plugin),
[Puppet](https://github.com/matthewbarr/puppet-zulip),
[Redmine](https://github.com/zulip/zulip-redmine-plugin), and
[Trello](https://github.com/zulip/trello-to-zulip);
[node.js API bindings](https://github.com/zulip/zulip-node); and our
[full-text search PostgreSQL extension](https://github.com/zulip/tsearch_extras).

We use [Transifex](https://www.transifex.com/zulip/zulip/) to do
translations.

In this overview, we'll mainly discuss the core Zulip server and web
application.

Usage assumptions and concepts
------------------------------

Zulip is a real-time web-based chat application meant for companies and
similar groups ranging in size from a small team to more than a thousand
users. It features real-time notifications, message persistence and
search, public group conversations (*streams*), private streams,
private one-on-one and group conversations, inline image previews, team
presence/buddy lists, a rich API, Markdown message support, and numerous
integrations with other services. The maintainer team aims to support
users who connect to Zulip using dedicated iOS, Android, Linux, Windows,
and macOS clients, as well as people using modern web browsers or
dedicated Zulip API clients.

A server can host multiple Zulip *realms* (organizations) at the same
domain, each of which is a private chamber with its own users,
streams, customizations, and so on. This means that one person might
be a user of multiple Zulip realms. The administrators of a realm can
choose whether to allow anyone to register an account and join, or
only allow people who have been invited, or restrict registrations to
members of particular groups (using email domain names or corporate
single-sign-on login for verification). For more on security
considerations, see [the security model section](../production/security-model.html).

The Zulip "All messages" screen is like a chronologically ordered inbox;
it displays messages, starting at the oldest message that the user
hasn't viewed yet (for more on that logic, see [the guide to the
pointer and unread counts](../subsystems/pointer.html)). The "All messages" screen displays
the most recent messages in all the streams a user has joined (except
for the streams they've muted), as well as private messages from other
users, in strict chronological order. A user can *narrow* to view only
the messages in a single stream, and can further narrow to focus on a
*topic* (thread) within that stream. Each narrow has its own URL. The
user can quickly see what conversation they're in -- the stream and
topic, or the names of the user(s) they're private messaging with
-- using *the recipient bar* displayed atop each conversation.

Zulip's philosophy is to provide sensible defaults but give the user
fine-grained control over their incoming information flow; a user can
mute topics and streams, and can make fine-grained choices to reduce
real-time notifications they find irrelevant.


Components
----------

  ![architecture-simple](../images/architecture_simple.png)

### Django and Tornado

Zulip is primarily implemented in the
[Django](https://www.djangoproject.com/) Python web framework.  We
also make use of [Tornado](http://www.tornadoweb.org) for the
real-time push system.

Django is the main web application server; Tornado runs the
server-to-client real-time push system. The app servers are configured
by the Supervisor configuration (which explains how to start the server
processes; see "Supervisor" below) and the nginx configuration (which
explains which HTTP requests get sent to which app server).

Tornado is an asynchronous server and is meant specifically to hold
open tens of thousands of long-lived (long-polling or websocket)
connections -- that is to say, routes that maintain a persistent
connection from every running client. For this reason, it's
responsible for event (message) delivery, but not much else. We try to
avoid any blocking calls in Tornado because we don't want to delay
delivery to thousands of other connections (as this would make Zulip
very much not real-time).  For instance, we avoid doing cache or
database queries inside the Tornado code paths, since those blocking
requests carry a very high performance penalty for a single-threaded,
asynchronous server system.  (In principle, we could do non-blocking
requests to those services, but the Django-based database libraries we
use in most of our codebase using don't support that, and in any case,
our architecture doesn't require Tornado to do that).

The parts that are activated relatively rarely (e.g. when people type or
click on something) are processed by the Django application server. One
exception to this is that Zulip uses websockets through Tornado to
minimize latency on the code path for **sending** messages.

There is detailed documentation on the
[real-time push and event queue system](../subsystems/events-system.html); most of
the code is in `zerver/tornado`.

#### HTML templates, JavaScript, etc.

Zulip's HTML is primarily implemented using two types of HTML
templates: backend templates (powered by the [Jinja2][] template
engine used for logged-out ("portico") pages and the webapp's base
content) and frontend templates (powered by [Handlebars][]) used for
live-rendering HTML from JavaScript for things like the main message
feed.

For more details on the frontend, see our documentation on
[translation](../translating/translating.html),
[templates](../subsystems/html-templates.html),
[directory structure](../overview/directory-structure.html), and
[the static asset pipeline](../subsystems/front-end-build-process.html).

[Jinja2]: http://jinja.pocoo.org/
[Handlebars]: http://handlebarsjs.com/

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
-   Requests to `/json/events`, `/api/v1/events`, and `/sockjs` are
    sent to the Tornado server. These are requests to the real-time push
    system, because the user's web browser sets up a long-lived TCP
    connection with Tornado to serve as [a channel for push
    notifications](https://en.wikipedia.org/wiki/Push_technology#Long_polling).
    nginx gets the hostname for the Tornado server via
    `puppet/zulip/files/nginx/zulip-include-frontend/upstreams`.
-   Requests to all other paths are sent to the Django app via the UNIX
    socket `unix:/home/zulip/deployments/uwsgi-socket` (defined in
    `puppet/zulip/files/nginx/zulip-include-frontend/upstreams`). We use
    `zproject/wsgi.py` to implement uWSGI here (see
    `django.core.wsgi`).
- By default (i.e. if `LOCAL_UPLOADS_DIR` is set), nginx will serve
  user-uploaded content like avatars, custom emoji, and uploaded
  files.  However, one can configure Zulip to store these in a cloud
  storage service like Amazon S3 instead.

### Supervisor

We use [supervisord](http://supervisord.org/) to start server processes,
restart them automatically if they crash, and direct logging.

The config file is
`zulip/puppet/zulip/templates/supervisor/zulip.conf.template.erb`. This
is where Tornado and Django are set up, as well as a number of background
processes that process event queues. We use event queues for the kinds
of tasks that are best run in the background because they are
expensive (in terms of performance) and don't have to be synchronous
--- e.g., sending emails or updating analytics. Also see [the queuing
guide](../subsystems/queuing.html).

### memcached

memcached is used to cache database model
objects. `zerver/lib/cache.py` and `zerver/lib/cache_helpers.py`
manage putting things into memcached, and invalidating the cache when
values change. The memcached configuration is in
`puppet/zulip/files/memcached.conf`.  See our
[caching guide](../subsystems/caching.html) to learn how this works in
detail.

### Redis

Redis is used for a few very short-term data stores, such as in the
basis of `zerver/lib/rate_limiter.py`, a per-user rate limiting scheme
[example](http://blog.domaintools.com/2013/04/rate-limiting-with-redis/)),
and the [email-to-Zulip
integration](https://zulipchat.com/integrations/doc/email).

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
`zulip/zerver/lib/queue.py`. There's an asynchronous client for use in
Tornado and a more general client for use elsewhere.  Most of the
processes started by Supervisor are queue processors that continually
pull things out of a RabbitMQ queue and handle them; they are defined
in `zerver/worker/queue_processors.py`.

Also see [the queuing guide](../subsystems/queuing.html).

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
`tools/provision`).  That file also manages setting up the
development postgresql user.

`tools/provision` also invokes `tools/do-destroy-rebuild-database`
to create the actual database with its schema.

### Thumbor and thumbnailing

We use Thumbor, a popular open source thumbnailing server, to serve
images (both for inline URL previews and serving uploaded image
files).  See [our thumbnailing docs](../subsystems/thumbnailing.html)
for more details on how this works.

### Nagios

Nagios is an optional component used for notifications to the system
administrator, e.g., in case of outages.

`zulip/puppet/zulip/manifests/nagios.pp` installs Nagios plugins from
`puppet/zulip/files/nagios_plugins/`.

This component is intended to install Nagios plugins intended to be run
on a Nagios server; most of the Zulip Nagios plugins are intended to be
run on the Zulip servers themselves, and are included with the relevant
component of the Zulip server (e.g.
`puppet/zulip/manifests/postgres_common.pp` installs a few under
`/usr/lib/nagios/plugins/zulip_postgres_common`).

## Glossary

This section gives names for some of the elements in the Zulip UI used
in Zulip development conversations.  Contributions to extend this list
are welcome!

* **chevron**: A small downward-facing arrow next to a message's
    timestamp, offering contextual options, e.g., "Reply", "Mute [this
    topic]", or "Link to this conversation". To avoid visual clutter,
    the chevron only appears in the web UI upon hover.

* **huddle**: What the codebase calls a "group private message".

* **message editing**: If the realm admin allows it, then after a user
    posts a message, the user has a few minutes to click "Edit" and
    change the content of their message. If they do, Zulip adds a
    marker such as "(EDITED)" at the top of the message, visible to
    anyone who can see the message.

* **realm**: What the codebase calls an "organization" in the UI.

* **recipient bar**: A visual indication of the context of a message
    or group of messages, displaying the stream and topic or private
    message recipient list, at the top of a group of messages. A
    typical 1-line message to a new recipient shows to the user as
    three lines of content: first the recipient bar, second the
    sender's name and avatar alongside the timestamp (and, on hover,
    the star and the chevron), and third the message content. The
    recipient bar is or contains hyperlinks to help the user narrow.

* **star**: Zulip allows a user to mark any message they can see,
    public or private, as "starred". A user can easily access messages
    they've starred through the "Starred messages" link in the
    left sidebar, or use "is:starred" as a narrow or a search
    constraint. Whether a user has or has not starred a particular
    message is private; other users and realm admins don't know
    whether a message has been starred, or by whom.

* **subject**: What the codebase calls a "topic" in many places.

* **bankruptcy**: When a user has been off Zulip for several days and
    has hundreds of unread messages, they are prompted for whether
    they want to mark all their unread messages as read.  This is
    called "declaring bankruptcy" (in reference to the concept in
    finance).
