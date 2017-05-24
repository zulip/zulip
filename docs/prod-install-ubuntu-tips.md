# Production Installation on Ubuntu

Here are some tips for installing the latest release Zulip on a production server running Ubuntu.

## Upstart

The latest releases of Ubuntu (later than 16.04 Xenial) have deprecated `upstart` in favor of systemd and having upstart installed on your system will interfere with the configuration and startup of the nginx server used by Zulip. So if your server isn't a clean install of nginx you may have upstart installed and will need to remove it before installing Zulip.

```shell
$ sudo apt remove upstart
```

## Puppet Port

To provision your server, the Zulip install script uses a Puppet service running on port 8140 in your server. So you'll need to configure your router and server to allow port 8140 incoming and outgoing tcp traffic.
