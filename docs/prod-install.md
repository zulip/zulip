# Production Installation

Make sure you want to install a Zulip production server; if you'd
instead like to test or develop a new feature, we recommend the
[Zulip server development environment](dev-overview.html#requirements) instead.

You will need an Ubuntu system that satisfies
[the installation requirements](prod-requirements.html).  In short,
you need:
* A Ubuntu 14.04 Trusty or Ubuntu 16.04 Xenial 64-bit server
* At least 2GB RAM and 10 GB disk space (4GB and 2 CPUs recommended for 100+ users).
* A DNS name, an SSL certificate, and credentials for sending email.

## Step 0: Subscribe

Please subscribe to low-traffic [the Zulip announcements Google
Group](https://groups.google.com/forum/#!forum/zulip-announce) to get
announcements about new releases, security issues, etc.

## Step 1: Install SSL Certificates

Zulip runs over https only and requires ssl certificates in order to
work. It looks for the certificates in `/etc/ssl/private/zulip.key`
and `/etc/ssl/certs/zulip.combined-chain.crt`.  Note that Zulip uses
`nginx` as its webserver and thus [expects a chained certificate
bundle](http://nginx.org/en/docs/http/configuring_https_servers.html)

If you need an SSL certificate, see [our SSL certificate
documentation](ssl-certificates.html).  If you already have an SSL
certificate, just install (or symlink) them into place at the above
paths, and move on to the next step.

## Step 2: Download and install latest release

If you haven't already, download and unpack [the latest built server
tarball](https://www.zulip.org/dist/releases/zulip-server-latest.tar.gz)
with the following commands:

```
sudo -i  # If not already root
cd /root
wget https://www.zulip.org/dist/releases/zulip-server-latest.tar.gz
rm -rf /root/zulip && mkdir /root/zulip
tar -xf zulip-server-latest.tar.gz --directory=/root/zulip --strip-components=1
```

Then, run the Zulip install script:
```
/root/zulip/scripts/setup/install
```

This may take a while to run, since it will install a large number of
dependencies. It also creates `zulip` user, which will be used to run
the various Zulip servers.

The Zulip install script is designed to be idempotent, so if it fails,
you can just rerun it after correcting the issue that caused it to
fail.  Also note that it automatically logs a transcript to
`/var/log/zulip/install.log`; please include a copy of that file in
any bug reports.

## Step 3: Configure Zulip

Configure the Zulip server instance by editing `/etc/zulip/settings.py` and
providing values for the mandatory settings, which are all found under the
heading `### MANDATORY SETTINGS`.

These settings include:

- `EXTERNAL_HOST`: the user-accessible Zulip domain name for your
  Zulip installation (aka what users will type in their web
  browser). This should of course match the DNS name you configured to
  point to your server and for which you configured SSL certificates.
  If you plan to use multiple domains, add the others to
  `ALLOWED_HOSTS`.

- `ZULIP_ADMINISTRATOR`: the email address of the person or team
  maintaining this installation and who will get support and error
  emails.

- `EMAIL_*`, `DEFAULT_FROM_EMAIL`, and `NOREPLY_EMAIL_ADDRESS`:
  credentials for an outgoing SMTP server so Zulip can send emails
  when needed (don't forget to set `email_password` in the
  `zulip-secrets.conf` file!).  We highly recommend reading our
  [production email docs](prod-email.html) and following the test
  procedure discussed there to make sure you've setup outgoing email
  correctly, since outgoing email is the most common configuration
  problem.

- `AUTHENTICATION_BACKENDS`: a list of enabled authentication
  mechanisms.  You'll need to enable at least one authentication
  mechanism by uncommenting its corresponding line, and then also do
  any additional configuration required for that backend as documented
  in the `settings.py` file (the email backend requires no extra
  configuration).  See the
  [section on Authentication](prod-authentication-methods.html) for
  more detail on the available authentication backends and how to
  configure them.

## Step 4: Initialize Zulip database

At this point, you are done doing things as root. The remaining
commands are run as the `zulip` user using `su zulip`. To initialize
the Zulip database for your production install, run:

```
su zulip -c /home/zulip/deployments/current/scripts/setup/initialize-database
```

The `initialize-database` script will report an error if you did not
fill in all the mandatory settings from `/etc/zulip/settings.py`.  It
is safe to rerun it after correcting the problem if that happens.

This completes the process of installing Zulip on your server.
However, in order to use Zulip, you'll need to create an organization
in your Zulip installation.

## Step 5: Create a Zulip organization and login

* If you haven't already, verify that your
  [outgoing email configuration works](prod-email.html#testing-and-troubleshooting).
  The organization creation process will fail if outgoing email is not
  configured properly.

* Run the organization (realm) creation [management
command](prod-maintain-secure-upgrade.html#management-commands) :

  ```
  su zulip # If you weren't already the zulip user
  /home/zulip/deployments/current/manage.py generate_realm_creation_link
  ```

  This will print out a secure 1-time use link that allows creation of a
  new Zulip organization on your server.  For most servers, you will
  only ever do this once, but you can run `manage.py
  generate_realm_creation_link` again if you want to host another
  organization on your Zulip server.

* Open the link generated with your web browser. You'll see the create
organization page ([screenshot here](_static/zulip-create-realm.png)).
Enter your email address and click *Create organization*.

* Check your email to find the confirmation email and click the
link. You'll be prompted to finish setting up your organization and
initial administrator user ([screenshot
here](_static/zulip-create-user-and-org.png)).  Complete this form and
log in!

**Congratulations!** You are logged in as an organization
administrator for your new Zulip organization.  After getting
oriented, we recommend visiting the "Organization settings" UI (linked
from the upper-right gear menu in the Zulip webapp) to configure
important policy settings like how users can join your new
organization. By default, your organization will be configured as
follows depending on what type of organization you selected:

Community Organization:
* `restricted_to_domain=False`: No restriction on user email addresses.
* `invite_required=True`: A user must be invited to join.

Corporate Organization:
* `restricted_to_domain=True`: New users must have an email address in the same domain (e.g. @acme.com) as yours.
* `invite_required=False`: No invitation is required to join.

Next, you'll likely want to do one of the following:

* [Customize your Zulip organization](prod-customize.html).
* [Learn about managing a production Zulip server](prod-maintain-secure-upgrade.html).

## Troubleshooting

If you get an error after `scripts/setup/install` completes, check
`/var/log/zulip/errors.log` for a traceback, and consult the
[troubleshooting section](prod-troubleshooting.html) for advice on how
to debug.  If that doesn't help, please visit
[#production help](https://chat.zulip.org/#narrow/stream/production.20help)
in the [Zulip developerment community server](chat-zulip-org.html) for
realtime help or email zulip-help@googlegroups.com with the full
traceback and we'll try to help you out!
