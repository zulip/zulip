# Authentication methods

Zulip supports several different authentications methods:

* `EmailAuthBackend` - Email/password authentication.
* `ZulipLDAPAuthBackend` - LDAP username/password authentication.
* `GoogleMobileOauth2Backend` - Google authentication.
* `GitHubAuthBackend` - GitHub authentication.
* `ZulipRemoteUserBackend` - Authentication using an existing
  Single-Sign-On (SSO) system that can set REMOTE_USER in Apache.
* `DevAuthBackend` - Only for development, passwordless login as any user.

It's easy to add more, see the docs on python-social-auth below.

The setup documentation for most of these is simple enough that we've
included it inline in `/etc/zulip/settings.py`, right above to the
settings used to configure them.  The remote user authentication
backend is more complex since it requires interfacing with a generic
third-party authentication system, and so we've documented it in
detail below.

## Adding additional methods using python-social-auth

The implementation for GitHubAuthBackend is a small wrapper around the
popular [python-social-auth] library.  So if you'd like to integrate
Zulip with another authentication provider (e.g. Facebook, Twitter,
etc.), you can do this by writing a class similar to
`GitHubAuthBackend` in `zproject/backends.py` and adding a few
settings.  Pull requests to add new backends are welcome; they should
be tested using the framework in `test_auth_backends.py`.

[python-social-auth]: http://psa.matiasaguirre.net/

## Remote User SSO Authentication

Zulip supports integrating with a Single-Sign-On solution.  There are
a few ways to do it, but this section documents how to configure Zulip
to use an SSO solution that best supports Apache and will set the
`REMOTE_USER` variable:

(0) Check that `/etc/zulip/settings.py` has
`zproject.backends.ZulipRemoteUserBackend` as the only enabled value
in the `AUTHENTICATION_BACKENDS` list, and that `SSO_APPEND_DOMAIN` is
correct set depending on whether your SSO system uses email addresses
or just usernames in `REMOTE_USER`.

Make sure that you've restarted the Zulip server since making this
configuration change.

(1) Edit `/etc/zulip/zulip.conf` and change the `puppet_classes` line to read:

```
puppet_classes = zulip::voyager, zulip::apache_sso
```

(2) As root, run `/home/zulip/deployments/current/scripts/zulip-puppet-apply`
to install our SSO integration.

(3) To configure our SSO integration, edit
`/etc/apache2/sites-available/zulip-sso.example` and fill in the
configuration required for your SSO service to set `REMOTE_USER` and
place your completed configuration file at `/etc/apache2/sites-available/zulip-sso.conf`

`zulip-sso.example` is correct configuration for using an `htpasswd`
file for `REMOTE_USER` authentication, which is useful for testing
quickly.  You can set it up by doing the following:

```
/home/zulip/deployments/current/scripts/restart-server
cd /etc/apache2/sites-available/
cp zulip-sso.example zulip-sso.conf
htpasswd -c /home/zulip/zpasswd username@example.com # prompts for a password
```

and then continuing with the steps below.

(4) Run `a2ensite zulip-sso` to enable the Apache integration site.

(5) Run `service apache2 reload` to use your new configuration.  If
Apache isn't already running, you may need to run `service apache2
start` instead.

Now you should be able to visit `https://zulip.example.com/` and
login via the SSO solution.


### Troubleshooting Remote User SSO

This system is a little finicky to networking setup (e.g. common
issues have to do with /etc/hosts not mapping settings.EXTERNAL_HOST
to the Apache listening on 127.0.0.1/localhost, for example).  It can
often help while debugging to temporarily change the Apache config in
/etc/apache2/sites-available/zulip-sso to listen on all interfaces
rather than just 127.0.0.1 as you debug this.  It can also be helpful
to change /etc/nginx/zulip-include/app.d/external-sso.conf to
proxy_pass to a more explicit URL possibly not over HTTPS when
debugging.  The following log files can be helpful when debugging this
setup:

* /var/log/zulip/{errors.log,server.log} (the usual places)
* /var/log/nginx/access.log (nginx access logs)
* /var/log/apache2/zulip_auth_access.log (you may want to change
  LogLevel to "debug" in the apache config file to make this more
  verbose)

Here's a summary of how the remote user SSO system works assuming
you're using HTTP basic auth; this summary should help with
understanding what's going on as you try to debug:

* Since you've configured /etc/zulip/settings.py to only define the
  zproject.backends.ZulipRemoteUserBackend, zproject/settings.py
  configures /accounts/login/sso as HOME_NOT_LOGGED_IN, which makes
  `https://zulip.example.com/` aka the homepage for the main Zulip
  Django app running behind nginx redirect to /accounts/login/sso if
  you're not logged in.

* nginx proxies requests to /accounts/login/sso/ to an Apache instance
  listening on localhost:8888 apache via the config in
  /etc/nginx/zulip-include/app.d/external-sso.conf (using the upstream
  localhost:8888 defined in /etc/nginx/zulip-include/upstreams).

* The Apache zulip-sso site which you've enabled listens on
  localhost:8888 and presents the htpasswd dialogue; you provide
  correct login information and the request reaches a second Zulip
  Django app instance that is running behind Apache with with
  REMOTE_USER set.  That request is served by
  `zerver.views.remote_user_sso`, which just checks the REMOTE_USER
  variable and either logs in (sets a cookie) or registers the new
  user (depending whether they have an account).

* After succeeding, that redirects the user back to / on port 443
  (hosted by nginx); the main Zulip Django app sees the cookie and
  proceeds to load the site homepage with them logged in (just as if
  they'd logged in normally via username/password).

Again, most issues with this setup tend to be subtle issues with the
hostname/DNS side of the configuration.  Suggestions for how to
improve this SSO setup documentation are very welcome!
