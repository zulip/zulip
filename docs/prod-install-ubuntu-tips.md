# Production Installation on Existing Ubuntu Server

Here are some tips for installing the latest release Zulip on a production server running Ubuntu. The Zulip installation scripts assume that it has carte blanche to overwrite your configuration files in /etc, so you probably don't want to install it on a server running other nginx or django apps. But if you do, here are some things you can do that may make it possible to retain your existing site. However, this is *NOT* recommended, and you may break your server. Make sure you have a provisioning script ready to go to wipe and restore your existing services if (when) your server goes down. 

## Nginx

Copy your existing nginx configuration to a backup and then merge the one created by Zulip into it:

```shell
$ sudo cp /etc/nginx/nginx.conf /etc/nginx.conf.before-zulip-install
$ wget https://raw.githubusercontent.com/zulip/zulip/master/puppet/zulip/files/nginx/nginx.conf -O /tmp/nginx.conf.zulip
$ sudo meld /etc/nginx/nginx.conf /tmp/nginx.conf.zulip  # be sure to merge to the right
```

After the zulip installation completes, then you can overwrite (or merge) your new nginx.conf with the installed one:

```shell
$ sudo meld /tmp/nginx.conf.zulip /etc/nginx/nginx.conf  # be sure to merge to the right
$ sudo service nginx restart 
```

Unfortunately Zulip expects the system user running the nginx server to be `zulip`, so you may have to refactor your other apps and what they expect to play nice with the new `zulip` user on your system.

## Upstart

The latest releases of Ubuntu (later than 16.04 Xenial) have deprecated `upstart` in favor of systemd and having upstart installed on your system will interfere with the configuration and startup of the nginx server used by Zulip. So if your server isn't a clean install of nginx you may have upstart installed and will need to remove it before installing Zulip.

```shell
$ sudo apt remove upstart
```

## Puppet

If you have a puppet server running on your server you will get an error message about not being able to connect to the client:

```shell
puppet-agent[29873]: Could not request certificate: Failed to open TCP connection to puppet:8140
```

So you'll need to shutdown any puppet servers.

```shell
$ sudo service puppet-agent stop
$ sudo service puppet stop
```
