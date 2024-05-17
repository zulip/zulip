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

Copy your existing nginx configuration to a backup and then merge the
one created by Zulip into it:

```bash
sudo cp /etc/nginx/nginx.conf /etc/nginx.conf.before-zulip-install
sudo curl -fL -o /etc/nginx/nginx.conf.zulip \
    https://raw.githubusercontent.com/zulip/zulip/main/puppet/zulip/templates/nginx.conf.template.erb
sudo meld /etc/nginx/nginx.conf /etc/nginx/nginx.conf.zulip  # be sure to merge to the right
```

Since the file in Zulip is an [ERB Puppet
template](https://puppet.com/docs/puppet/7/lang_template_erb.html),
you will also need to replace any `<%= ... %>` sections with
appropriate content. For instance `<%= @ca_crt %>` should be replaced
with `/etc/ssl/certs/ca-certificates.crt` on Debian and Ubuntu
installs.

After the Zulip installation completes, then you can overwrite (or
merge) your new nginx.conf with the installed one:

```console
$ sudo meld /etc/nginx/nginx.conf.zulip /etc/nginx/nginx.conf  # be sure to merge to the right
$ sudo service nginx restart
```

Zulip's Puppet configuration will change the ownership of
`/var/log/nginx` so that the `zulip` user can access it. Depending on
your configuration, this may or may not cause problems.

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

Zulip expects to install PostgreSQL 12, and find that listening on
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
