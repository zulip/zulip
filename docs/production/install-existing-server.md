```eval_rst
:orphan:
```

# Production Installation on Existing Server

Here are some tips for installing the latest release Zulip on a
production server running Debian or Ubuntu. The Zulip installation
scripts assume that it has carte blanche to overwrite your
configuration files in /etc, so we recommend against installing it on
a server running other nginx or django apps.

But if you do, here are some things you can do that may make it
possible to retain your existing site. However, this is *NOT*
recommended, and you may break your server. Make sure you have backups
and a provisioning script ready to go to wipe and restore your
existing services if (when) your server goes down.

These instructions are only for experts.  If you're not an experienced
Linux sysadmin, you will have a much better experience if you get a
dedicated VM to install Zulip on instead (or [use zulipchat.com](https://zulipchat.com).

### Nginx

Copy your existing nginx configuration to a backup and then merge the
one created by Zulip into it:

```shell
sudo cp /etc/nginx/nginx.conf /etc/nginx.conf.before-zulip-install
sudo wget -O /etc/nginx/nginx.conf.zulip \
    https://raw.githubusercontent.com/zulip/zulip/master/puppet/zulip/files/nginx/nginx.conf
sudo meld /etc/nginx/nginx.conf /etc/nginx/nginx.conf.zulip  # be sure to merge to the right
```

After the zulip installation completes, then you can overwrite (or
merge) your new nginx.conf with the installed one:

```shell
$ sudo meld /etc/nginx/nginx.conf.zulip /etc/nginx/nginx.conf  # be sure to merge to the right
$ sudo service nginx restart
```

Zulip's puppet configuration will change the ownership of
`/var/log/nginx` so that the `zulip` user can access it.  Depending on
your configuration, this may or may not cause problems.

### Puppet

If you have a puppet server running on your server, you will get an
error message about not being able to connect to the client during the
install process:

```shell
puppet-agent[29873]: Could not request certificate: Failed to open TCP connection to puppet:8140
```

So you'll need to shutdown any puppet servers.

```shell
$ sudo service puppet-agent stop
$ sudo service puppet stop
```

### Postgres

If you have an existing postgres database, note that Zulip will use
the default `main` as its database name; make sure you're not using
that.

### Memcached, redis, and rabbitmq

Zulip will, by default, configure these services for its use.  The
configuration we use is pretty basic, but if you're using them for
something else, you'll want to make sure the configurations are
compatible.

### No uninstall process

We don't provide a convenient way to uninstall a Zulip server.

## No support, but contributions welcome!

Most of the limitations are things we'd accept a pull request to fix;
we welcome contributions to shrink this list of gotchas.  Chat with us
in the [chat.zulip.org community](../contributing/chat-zulip-org.html) if you're
interested in helping!
