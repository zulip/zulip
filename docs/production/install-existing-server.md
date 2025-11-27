---
orphan: true
---

# Production installation on an existing server

Here are some tips for installing the latest release of Zulip on a
production server running Debian or Ubuntu. The Zulip installation
scripts assume that it has carte blanche to overwrite your
configuration files in /etc, so we recommend against installing it on
a server running other nginx or django apps.

But if you do, here are some things you can do that may make it
possible to retain your existing site. However, this is _NOT_
recommended, and you may break your server. Make sure you have backups
and a provisioning script ready to go to wipe and restore your
existing services if (when) your server goes down.

These instructions are only for experts. If you're not an experienced
Linux sysadmin, you will have a much better experience if you get a
dedicated VM to install Zulip on instead (or [use
zulip.com](https://zulip.com)).

### nginx

**Good news**: As of recent versions, Zulip no longer modifies
`/etc/nginx/nginx.conf`, so your existing nginx configuration will be preserved.
Zulip creates its configuration as a site-specific file in
`/etc/nginx/sites-available/zulip-enterprise`, which is linked to `sites-enabled`.
This means:

- The nginx user remains as your system default (typically `www-data`)
- Your existing nginx.conf is not modified
- Other sites should continue to work without issues

Zulip's Puppet configuration will:

- Create `/etc/nginx/sites-available/zulip-enterprise` with Zulip's site
  configuration
- Add the `zulip` user to the `adm` group to read nginx logs
- Set `/var/log/nginx` ownership to `www-data:adm` (so nginx can write, zulip
  can read)
- Create Zulip-specific include files in `/etc/nginx/zulip-include/`
- Remove `/etc/nginx/sites-enabled/default` if it exists

If you have a custom nginx configuration that conflicts with Zulip's site
configuration, you may need to adjust server names or ports in Zulip's site
config.

Depending on how you have configured `nginx` for your other services,
you may need to add a `server_name` for the Zulip `server` block in
the `nginx` configuration.

### Puppet

If you have a Puppet server running on your server, you will get an
error message about not being able to connect to the client during the
install process:

```console
puppet-agent[29873]: Could not request certificate: Failed to open TCP connection to puppet:8140
```

So you'll need to shut down any Puppet servers.

```console
$ sudo service puppet-agent stop
$ sudo service puppet stop
```

### PostgreSQL

Zulip expects to install PostgreSQL 16, and find that listening on
port 5432; any other version of PostgreSQL that is detected at install
time will cause the install to abort. If you already have PostgreSQL
installed, you can pass `--postgresql-version=` to the installer to
have it use that version. It will replace the package with the latest
from the PostgreSQL apt repository, but existing data will be
retained.

If you have an existing PostgreSQL database, note that Zulip will use
the default `main` as its database name; make sure you're not using
that.

### Memcached, Redis, and RabbitMQ

Zulip will, by default, configure these services for its use. The
configuration we use is pretty basic, but if you're using them for
something else, you'll want to make sure the configurations are
compatible.

### No uninstall process

We don't provide a convenient way to uninstall a Zulip server.

## No support, but contributions welcome!

Most of the limitations are things we'd accept a pull request to fix;
we welcome contributions to shrink this list of gotchas. Chat with us
in the [chat.zulip.org community](https://zulip.com/development-community/) if you're
interested in helping!
