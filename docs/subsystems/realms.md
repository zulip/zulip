# Realms in Zulip

Zulip allows multiple _realms_ to be hosted on a single instance.
Realms are the Zulip codebase's internal name for what we refer to in
user-facing documentation as an organization (the name "realm" comes
from [Kerberos](https://web.mit.edu/kerberos/)).

Wherever possible, we avoid using the term `realm` in any user-facing
string or documentation; "Organization" is the equivalent term used in
those contexts (and we have linters that attempt to enforce this rule
in translatable strings). We may in the future modify Zulip's
internals to use `organization` instead.

The
[production docs on multiple realms](../production/multiple-organizations.md)
are also relevant reading.

## Creating realms

There are two main methods for creating realms.

- Using unique link generator
- Enabling open realm creation

#### Using unique link generator

```bash
./manage.py generate_realm_creation_link
```

The above command will output a URL which can be used for creating a
new realm and an administrator user for that realm. The link expires
after the creation of the realm. The link also expires if not used
within 7 days. The expiration period can be changed by modifying
`REALM_CREATION_LINK_VALIDITY_DAYS` in settings.py.

## Subdomains

One can host multiple realms in a Zulip server by giving each realm a
unique subdomain of the main Zulip server's domain. For example, if
the Zulip instance is hosted at zulip.example.com, and the subdomain
of your organization is acme you can would acme.zulip.example.com for
accessing the organization.

For subdomains to work properly, you also have to change your DNS
records so that the subdomains point to your Zulip installation IP. An
`A` record with host name value `*` pointing to your IP should do the
job.

We also recommend upgrading to at least Zulip 1.7, since older Zulip
releases had much less nice handling for subdomains. See our
[docs on using subdomains](../production/multiple-organizations.md) for
user-facing documentation on this.

### Working with subdomains in development environment

Zulip's development environment is designed to make it convenient to
test the various Zulip configurations for different subdomains:

- Realms are subdomains on `*.zulipdev.com`, just like `*.zulipchat.com`.
- The root domain (like `zulip.com` itself) is `zulipdev.com` itself.
- The default realm is hosted on `localhost:9991` rather than
  `zulip.zulipdev.com`, using the [`REALM_HOSTS`
  feature](../production/multiple-organizations.md) feature.

Details are below.

By default, Linux does not provide a convenient way to use subdomains
in your local development environment. To solve this problem, we use
the **zulipdev.com** domain, which has a wildcard A record pointing to
127.0.0.1. You can use zulipdev.com to connect to your Zulip
development server instead of localhost. The default realm with the
Shakespeare users has the subdomain `zulip` and can be accessed by
visiting **zulip.zulipdev.com**.

If you are behind a **proxy server**, this method won't work. When you
make a request to load zulipdev.com in your browser, the proxy server
will try to get the page on your behalf. Since zulipdev.com points
to 127.0.0.1 the proxy server is likely to give you a 503 error. The
workaround is to disable your proxy for `*.zulipdev.com`. The DNS
lookup should still work even if you disable proxy for
\*.zulipdev.com. If it doesn't you can add zulipdev.com records in
`/etc/hosts` file. The file should look something like this.

```text
127.0.0.1    localhost

127.0.0.1    zulipdev.com

127.0.0.1    zulip.zulipdev.com

127.0.0.1    testsubdomain.zulipdev.com
```

These records are also useful if you want to, for example, run the
Puppeteer tests when you are not connected to the Internet.
