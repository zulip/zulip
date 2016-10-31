# Realms in Zulip

Zulip allows multiple *realms* to be hosted on a single instance. You can
think of a realm as an organization.

## Creating Realms

There are mainly two methods for creating realms.

* Using unique link generator
* Enabling open realm creation

#### Using Unique Link Generator

```bash
    ./manage.py generate_realm_creation_link
```
The above command will ouput a URL which can be used for creating a new realm
and an admin user. The link would expire after the creation of the realm.
The link would also expire if not used within 7 days. The expiration period
can be changed by modifying `REALM_CREATION_LINK_VALIDITY_DAYS` in settings.py.

### Enabling Open Realm Creation

If you want public to create new realms you can enable Open Realm Creation.
This will add a **Create new organization** link to your Zulip homepage
and anyone can create a new realm by visiting this link (**/create_realm**).
This feature is disabled by default in production instances and can be
enabled by setting `OPEN_REALM_CREATION` to True in settings.py.

## Subdomains

Each realm can have a unique subdomain. For example if the Zulip
instance is hosted at zulipchat.com and the subdomain of your organization
is acme you can use acme.zulipchat.com for accessing the organization.
Subdomains are not enabled by default. You can enable subdomains by setting
the value of `REALMS_HAVE_SUBDOMAINS` to True in settings.py. For subdomains
to work properly you also have to change your DNS records so that the subdomains
point to your Zulip installation IP. An `A` record with host name value `*`
pointing to your IP should do the job.

### Working With Subdomains In Development Evironment

Since by default there is no way of handling subdomains in your local development
environment we use **zulipdev.com** domain which has a wildcard A record pointing to
127.0.0.1. When `REALMS_HAVE_SUBDOMAINS` is set to True you should use zulipdev.com
instead of localhost. The default realm have the subdomain Zulip and can be accessed
by visiting **zulip.zulipdev.com**. You should also change the value of `EXTERNAL_HOST`
from "localhost:9991" to "zulipdev.com:9991" when using subdomains.

If you are behind a **proxy server** this method won't work. When you make a request to
load zulipdev.com in browser the proxy server will try to get the page on your behalf.
Since zulipdev.com points to 127.0.0.1 the proxy server is likely to give you a 503 error.
The workaround is to disable proxy for `*.zulipdev.com`. The DNS lookup should still work
even if you disable proxy for *.zulipdev.com. If it doesn't you can add zulipdev.com
records in `/etc/hosts` file. The file should look something like this.

 ```
127.0.0.1    localhost

127.0.0.1    zulipdev.com

127.0.0.1    zulip.zulipdev.com

127.0.0.1    testsubdomain.zulipdev.com
```

These records are also useful when you are not connected to the network.
