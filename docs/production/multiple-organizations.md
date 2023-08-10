# Hosting multiple organizations

The vast majority of Zulip servers host just a single organization (or
"realm", as the Zulip code calls organizations). This article
documents what's involved in hosting multiple Zulip organizations on a
single server.

Throughout this article, we'll assume you're working on a Zulip server
with hostname `zulip.example.com`. You may also find the more
[technically focused article on realms](../subsystems/realms.md) to be useful
reading.

## Subdomains

Zulip's approach for supporting multiple organizations on a single
Zulip server is for each organization to be hosted on its own
subdomain. E.g. you'd have `org1.zulip.example.com` and
`org2.zulip.example.com`.

Web security standards mean that one subdomain per organization is
required to support a user logging into multiple organizations on a
server at the same time.

When you want to create a new organization, you need to do a few
things:

- If you're using Zulip older than 1.7, you'll need to set
  `REALMS_HAVE_SUBDOMAINS=True` in your `/etc/zulip/settings.py`
  file. That setting is the default in 1.7 and later.
- Make sure you have SSL certificates for all of the subdomains you're
  going to use. If you're using
  [our Let's Encrypt instructions](ssl-certificates.md), it's easy to
  just specify multiple subdomains in your certificate request.
- If necessary, modify your `nginx` configuration to use your new
  certificates.
- Use `./manage.py generate_realm_creation_link` again to create your
  new organization. Review
  [the install instructions](install.md) if you need a
  refresher on how this works.
- If you're planning on using GitHub auth or another social
  authentication method, review
  [the notes on `SOCIAL_AUTH_SUBDOMAIN` below](#authentication).

### SSL certificates

You'll need to install an SSL certificate valid for all the
(sub)domains you're using your Zulip server with. You can get an SSL
certificate covering several domains for free by using
[our Certbot wrapper tool](ssl-certificates.md#after-zulip-is-already-installed),
though if you're going to host a large number of organizations, you
may want to get a wildcard certificate. You can also get a wildcard
certificate for
[free using Certbot](https://community.letsencrypt.org/t/getting-wildcard-certificates-with-certbot/56285),
but because of the stricter security checks for acquiring a wildcard
cert, it isn't possible for a generic script like `setup-certbot` to
create it for you; you'll have to do some manual steps with your DNS
provider.

### Other hostnames

If you'd like to use hostnames that are not subdomains of each other,
you can set the `REALM_HOSTS` setting in `/etc/zulip/settings.py` to a
Python dictionary, like this:

```python
REALM_HOSTS = {
    "mysubdomain": "hostname.example.com",
}
```

This will make `hostname.example.com` the hostname for the realm that
would, without this configuration, have been
`mysubdomain.zulip.example.com`. To create your new realm on
`hostname.example.com`, one should enter `mysubdomain` as the
"subdomain" for the new realm.

The value you choose for `mysubdomain` will not be displayed to users;
the main constraint is that it will be impossible to create a
different realm on `mysubdomain.zulip.example.com`.

In a future version of Zulip, we expect to move this configuration
into the database.

### The root domain

Most Zulip servers host a single Zulip organization on the root domain
(e.g. `zulip.example.com`). The way this is implemented internally
involves the organization having the empty string (`''`) as its
"subdomain".

You can mix having an organization on the root domain and some others
on subdomains (e.g. `subdivision.zulip.example.com`), but this only
works well if there are no users in common between the two
organizations, because the auth cookies for the root domain are
visible to the subdomain (so it's not possible for a single
browser/client to be logged into both). So we don't recommend that
configuration.

### Changing subdomains

You can [change the subdomain][help-center-change-url] for an existing
organization using a [management command][management-commands]. Be
sure you understand the implications of changing the organization URL
before doing so, as it can be disruptive to users.

[management-commands]: ../production/management-commands.md
[help-center-change-url]: https://zulip.com/help/change-organization-url

### Authentication

Many of Zulip's supported authentication methods (Google, GitHub,
SAML, etc.) can require providing the third-party authentication
provider with a whitelist of callback URLs to your Zulip server (or
even a single URL). For those vendors that support a whitelist, you
can provide the callback URLs for each of your Zulip organizations.

The cleaner solution is to register a special subdomain, e.g.
`auth.zulip.example.com` with the third-party provider, and then set
`SOCIAL_AUTH_SUBDOMAIN = 'auth'` in `/etc/zulip/settings.py`, so that
Zulip knows to use that subdomain for these authentication callbacks.

### The system bot realm

This is very much an implementation detail, but worth documenting to
avoid confusion as to why there's an extra realm when inspecting the
Zulip database.

Every Zulip server comes with 1 realm that isn't created by users: the
`zulipinternal` realm. By default, this realm only contains the Zulip "system
bots". You can get a list of these on your system via
`./scripts/get-django-setting INTERNAL_BOTS`, but this is where bots
like "Notification Bot", "Welcome Bot", etc. exist. In the future,
we're considering moving these bots to exist in every realm, so that
we wouldn't need the system realm anymore.

### Migrating / troubleshooting

If you're migrating from a configuration using the root domain to one
with realms hosted on subdomains, be sure to clear cookies in any
browsers that were logged in on the root domain; otherwise, those
browsers will experience weird/confusing redirects.

## Open realm creation

Installations like [Zulip Cloud](https://zulip.com/plans/) that wish to
allow anyone on the Internet to create new Zulip organizations can do
so by setting `OPEN_REALM_CREATION = True` in
`/etc/zulip/settings.py`. Note that offering Zulip hosting to anyone
on the Internet entails significant responsibility around security,
abuse/spam, legal issues like GDPR/CCPA compliance, and more.
