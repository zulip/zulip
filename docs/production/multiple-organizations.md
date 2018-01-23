```eval_rst
:orphan:
```

# Hosting multiple organizations

The vast majority of Zulip servers host just a single organization (or
"realm", as the Zulip code calls organizations).  This article
documents what's involved in hosting multiple Zulip organizations on a
single server.

Throughout this article, we'll assume you're working on a zulip server
with hostname `zulip.example.com`.  You may also find the more
[technically focused article on realms](../subsystems/realms.html) to be useful
reading.

## Subdomains

Zulip's approach for supporting multiple organizations on a single
Zulip server is for each organization to be hosted on its own
subdomain.  E.g. you'd have `org1.zulip.example.com` and
`org2.zulip.example.com`.

Web security standards mean that one subdomain per organization is
required to support a user logging into multiple organizations on a
server at the same time.

When you want to create a new organization, you need to do a few
things:

* If you're using Zulip older than 1.7, you'll need to set
  `REALMS_HAVE_SUBDOMAINS=True` in your `/etc/zulip/settings.py`
  file.  That setting is the default in 1.7 and later.
* Make sure you have SSL certificates for all of the subdomains you're
  going to use.  If you're using
  [our LetsEncrypt instructions](ssl-certificates.html), it's easy to
  just specify multiple subdomains in your certificate request.
* If necessary, modify your `nginx` configuration to use your new
  certificates.
* Use `./manage.py generate_realm_creation_link` again to create your
  new organization.  Review
  [the install instructions](install.html) if you need a
  refresher on how this works.

For servers hosting a large number of organizations, like
[zulipchat.com](https://zulipchat.com), one can set
`ROOT_DOMAIN_LANDING_PAGE = True` in `/etc/zulip/settings.py` so that
the homepage for the server is a copy of the Zulip homepage.

### The root domain

Most Zulip servers host a single Zulip organization on the root domain
(i.e. `zulip.example.com`).  The way this is implemented internally
involves the organization having the empty string (`''`) as its
"subdomain".  You can mix having an organization on the root domain
and some others on subdomains (e.g. `it.zulip.example.com`).

### The system bot realm

This is very much an implementation detail, but worth documenting to
avoid confusion as to why there's an extra realm when inspecting the
Zulip database.

Every Zulip server comes with 1 realm that isn't created by users: the
`zulip` realm.  By default, this realm only contains the Zulip "system
bots".  You can get a list of these on your system via
`./scripts/get-django-setting INTERNAL_BOTS`, but this is where bots
like "Notification Bot", "Welcome Bot", etc. exist.  In the future,
we're considering moving these bots to exist in every realm, so that
we wouldn't need the system realm anymore.
