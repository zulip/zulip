# Zulip's files and directories

In this documentation, Zulip's technologies and file systems are combined to
help readers have a strong grasp of strength and weakeness of basic technologies used in Zulip open
source project.

## Django web framework

- Advantages:

  - As Python is the main programming language used in Zulip, choose Django web framework is an advantage.
    Django allows Zulip project to have multiple applications.
    In addition, Zulip utilizes some functionalities offered by Django including database migration,
    user authentication, admin, and robust cache framework. Another advantage is the machine learning
    capability, which could bring more attractive new features for Zulip project.

- Disavantages:
  - Django web framework requires some bandwidth that seems to be unfavorable for small-scaled project with
    few features. Another major problem is that Django is unable to handle multiple requests simultaneously.
- Structure:
  - `manage.py` sets the `DJANGO_SETTINGS_MODULE` environment variable to point to setting.py
  - `settings.py` is the Django settings to configure Django project
  - `urls.py` is uded to define URLs for Django projects
  - `wsgi.py`is used to develop the Django WSGI application object; WSGI is the primary deployment platform
    of Django project.

```
zulip/
    manage.py
    zproject/
        __init__.py
        settings.py
        urls.py
        wsgi.py
```

### Zulip applications

The Django web framework allows Zulip project to host many applications.

- Each application has a `migration directory` containing migration files written in Python.
  Migration functionality of the Django web framework allows customized changes to the model.
  Migration objects has two common attributes: dependencies and operations.
- `views directory` contains Python files; each of those files defines Python
  functions which takes HttpRequest and returns HttpResponse

#### zerver application

Structure:

- `apps.py` defines the `AppConfig` subclass for a Django application; otherwise, Django will
  use the AppConfig class.

- `models.py` creates `models`, which is a` Django.db` subclass. Models define fields of a database
  table in Django.

```
    zerver/
        __init__.py
        apps.py
        migrations/
        models.py
        tests/
        views/
```

# Tornado web framework

- Advantages: - Tornado offers advantages that Django does not have: the
  asynchronous, non-blocking network I/O with a single-threaded event loop.
  This helps Zulip chat app can scale to thousands of long-lived connections.
  Furthermore, Tornado supports the multilingual web application, which is also one of
  Zulip's product features.

- Structure:
  - The Tornado web framework locates in the zerver app
  - `application.py` defines the Tornado web application
  - `handlers.py` creates the `AsyncDjangoHandler` class which inherits the `tornado.web.RequestHandler`
  - `django_api.py` defines the `TornadoAdapter` class which inherits the HTTPAdapter
  - `event_queue.py` defines the `EventQueue` class with methods such as push, pop, empty,
    and contents to manage the EventQueue

```
    zulip/
        puppet/
            zulip/
                manifest/
                    tornado_sharding.pp
        zerver/
            tornado/
                __init__.py
                application.py
                handlers.py
                django_api.py
                event_queue.py

```

# Webhooks

- Advantages:
  - Using Webhooks, Zulip's users can receive data from other third-party
    services in real-time when predefined events happens.
- Disadvantages: - This established communication is one-way and only allow users to receive data. Thus,
  users can not update, delete, or send data.
- Structure:
  - The Webhooks locates in the zerver app.
  - `common.py` imports the `gettext module` from `Django.utils.translation` to translate `translation strings`
    into the end user's language given that there exists a translation for this string in user's language.
  - Each subdirectory in the webhooks directory has a `view.py` file, which handles HttpRequest and
    HttpResonse for the webhook.

```
    zerver/
        webhooks/
        decorator.py

        decorator
        lib/
            webhooks/
                common.py

```

# NGINX

- Advantages:

  - NGINX as `reverse proxy server` for HTTP, HTTPS, SMTP, IMAP, POP3 protocols. NGINX is also
    the email proxy for IMAP, POP3, and SMTP protocol. NGINX features HTTP load balancer,
    HTTP cache, and Web Sockets.
  - NGINX is asynchronous event-driven. In addition, NGINX is single threaded but handle multiple
    connections. Therefore, NGINX support the Zulip app chat by boosting high performance even
    under heavy network traffic.

- Disadvantages:
  - For dynamic contents, NGINX requires external programs to handle them. Besides, NGINX has
    fewer number of modules than Apache has. NGINX offers limited support for Windows.
- Structure:
  - In NGINX, the `master process` reads nginx configuration files and manage worker processes while
    `worker processes` actually dealt with requests.
  - NGINX configuration files locates at `zulip/puppet/zulip/files/nginx/`.
    **Notably, NGINX is used in Zulip's production, not in Zulip's development**
  - The `upstream` are upstream servers to which requests are distributed. 
  - `uploads.types` defines types of upload files. 
  - `app` sets the configuration depending on the requested URI. 
  - URLs request to `/static/` are managed by `zulip/prod-static` 
  - URLs requests to `/json/events` or `/api/v1/events` are handled by Tornado server. 
  - Other URLs requests such as `/thumbnail, /avatar, /user_uploads, /api` are sent to Django via uWSGI.

```
    zulip/
        puppet/
            zulip/
                files/
                    nginx/
                        manifests/
                            nginx.pp
                        zulip-include-frontend/
                            upstream
                            uploads.types
                            app

                    supervisor/
                        conf.d/
                            nginx.conf
```

# RabbitMQ

- Advantages:
  - RabbitMQ opens connection, establish channel to accept messages and then queue those messages.
    In-queue messages is then forwarded to their destinations for processing.
    Connection is closed after finishing.
  - RabbitMQ can work with multiple protocols. RabittMQ have many clients in different programming
    languages. For Python client, Pika is recommended.
- Structure:
  - `configure-rabbitmq` sets RabbitMQ username and password, wait for Rabbitmq to start up.
  - `rabbitmq-env.conf` setup default NODENAME = zulip@localhost, NODE_IP_ADDRESS = 127.0.0.1,
    and NODE_PORT = 5672 for rabbbitmq network.
  - `rabbitqm.conf` is the configuration for TCP listener.
  - `queue.py` defines class `SimpleQueueClient` and class `TornadoQueueClient`.
    Both of those two classes inherit from the class `QueueClient` to setup Rabbitmq credentials, which
    then is used to establish connection and channel using `Pika Python client`.
    Different from the SimpleQueueClient, the TornadoQueueClient uses the the `tornado.ioloop library`
    to build a asynchronous client.

```
    zulip/
        scripts/
            setup/
                configure-rabbitmq


        /puppet/
            zulip/
                files/
                    rabbitmq/
                        rabbitmq-env.conf
                        rabbitmq.config

        /zerver
            lib/
                queue.py
            worker/
                queue_processors.py

```

# PostgreSQL

- Advantages:
  - Django supports many databases such as PostgreSQL, MariaDB, MySQL, Oracle, and SQLite,
    but PostgreSQL is prefered to store persistent database in Django web app.
    PostgreSQL is an object-relational database system.
    PostgreSQL allows user-defined datatypes and support for both SQL and JSON queries.
- Structure:
  - `env_wal_g` configures for `PGHOST, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY`.
  - `pg_backup_and_purge` runs `env_wal_g`, `backup_push`, and `pg_data_path`
  - `process_fts_updates` establishes database queries to updates, delete, or select from database.
    Different `config_files` are used depending on which users (zulip, nagios_user).
  - `rebuild-dev-database`: setup PGHOST as localhost for development purpose.

```
    zulip/
        scripts/
        puppet/
            zulip/
                files/
                    postgreSQL/
                        env_wal_g
                        pg_backup_and_purge
                        process_fts_updates

                manifest/
                    postgresql_backups.pp
                    postgresql_base.pp
                    postgresql_common.pp

        /tools
            rebuild-dev-database
            rebuild-test-database

```

# Nagios

- Advantages:
  - Nagios is the continuous monitoring tool for application, server, and network.
    Developers can customize scripts to extend the monitor services.
- Disadvantages:
  - Some features are not available on the free version. Also, Nagios
    simply monitor network but can not manage the network. Nagio can not monitor the used
    or available bandwidth.
- Structure:
  - Zulip `nagios_plugins` runs on the Zulip servers to check for zulip application, postgresql,
    postgresql backup, rabbitml, and debian packages.
  - `postgresql_backup.pp` requires `nagios_plugins` package

```
    zulip/
        /scrips/
            nagios/
                check-rabbitmq-consumers
                check-rabbitmq-queue

        puppet/
            zulip/
                manifests/
                    postgresql_backups.pp

                files/
                    nagios_plugins/

                        zulip_base/check_debian_packages

                        zulip_postgresql/check_postgresql_replication_lag

                        zulip_postgresql_backup/check_postgresql_backup

                        zulip_app_frontend/
                            check_cron_file
                            check_queue_worker_errors
                            check_send_receive_time
                            check_worker_memory
```

# Memcached

- Advantages:
  - Memcached optimizes the performance and scalablitiy by using memory-based cache server
    to handle small chunks of arbitrary data that previously received from API calls or database.
- Structure:
  - `cache.py` and `cache_helpers.py` defines classes and methods to manage cache.
  - `mecached.conf` congigures memcached.

```
    zulip/
        puppet/
            zulip/files/sasl2/
                memcached.conf

        zerver/
            lib/
                cache.py
                cache_helpers.py

```

# Supervisord

- Advantage:
  - Supervisord allows to control multiple processes on UNIX- like operating system.
    Supervisord start processes as subprocesses via fork/exec and can restart the
    project's server subprocesses when crash occurs.
- Structure:
  - `supervisor.pp` defines the supervisor class and manage `supervisor_services`.
  - `nginx.conf`set commands to start NGINX webserver.
  - `zulip_db.conf` set commands to start `process_fts_updates`.

```
    zulip/
        puppet
            /zulip/
                manifests/
                    supervisor.pp
                files/
                    supervisor/
                        conf.d/
                            nginx.conf
                            zulip_db.conf
                            cron.conf

```

# Puppet

- Advantages:
  - Puppet is a configuration tool used by administrator to set system congfiguration across systems.
    In addition, Puppet can be used to periodically schedule specific maintenance work.
    Puppet supports many platforms such as Debian, Solaris, OS X, and Windows.
- Disadvantage:
  - Developers need to learn Ruby programming language to extend Puppet.
  - The Puppet's transaction reports are not comprehensive.
- Structure:
  - There is one Puppet server and many Puppet agents.
  - `conf.d` directory is the server configuration files or `Puppet server`.
  - The Puppet sever uses `manifest files` defined in `manifests` directory when
    booting up and compiling.
  - The Puppet `templates` directory consists of files written in ERB, a Ruby standard
    library. Puppet templates access Puppet variables to populate contents of configuration file.
  - Puppet server uses a `file server` defined in `files` directory to send
    static files' results to `Puppet agent`.

```
    zulip/
        puppet/
            zulip/
                files/
                    supervisor/
                        conf.d/
                manifests/
                templates

            zulip_ops/
                files/
                manifests/
                templates/
```
