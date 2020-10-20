# Authentication methods

Zulip supports a wide variety of authentication methods.  Some of them
require configuration to set up.

To configure or disable authentication methods on your Zulip server,
edit the `AUTHENTICATION_BACKENDS` setting in
`/etc/zulip/settings.py`, as well as any additional configuration your
chosen authentication methods require; then restart the Zulip server.

Details on each method below.

## Email and password

The `EmailAuthBackend` method is the one method enabled by default,
and it requires no additional configuration.

Users set a password with the Zulip server, and log in with their
email and password.

When first setting up your Zulip server, this method must be used for
creating the initial realm and user.  You can disable it after that.

## Plug-and-play SSO (Google, GitHub, GitLab)

With just a few lines of configuration, your Zulip server can
authenticate users with any of several single-sign-on (SSO)
authentication providers:
* Google accounts, with `GoogleAuthBackend`
* GitHub accounts, with `GitHubAuthBackend`
* GitLab accounts, with `GitLabAuthBackend`
* Microsoft Azure Active Directory, with `AzureADAuthBackend`

Each of these requires one to a handful of lines of configuration in
`settings.py`, as well as a secret in `zulip-secrets.conf`.  Details
are documented in your `settings.py`.

## SAML

Zulip 2.1 and later supports SAML authentication, used by Okta,
OneLogin, and many other IdPs (identity providers).  You can configure
it as follows:

1. These instructions assume you have an installed Zulip server; if
   you're using Zulip Cloud, see [this article][saml-help-center],
   which also has IdP-side configuration advice for common IdPs.

   You can have created a Zulip organization already using the default
   EmailAuthBackend, or plan to create the organization using SAML
   authentication.

1. Tell your IdP how to find your Zulip server:

    * **SP Entity ID**: `https://yourzulipdomain.example.com`.

      The `Entity ID` should match the value of
      `SOCIAL_AUTH_SAML_SP_ENTITY_ID` computed in the Zulip settings.
       You can get the correct value by running the following:
      `/home/zulip/deployments/current/scripts/get-django-setting
       SOCIAL_AUTH_SAML_SP_ENTITY_ID`.

    * **SSO URL**:
      `https://yourzulipdomain.example.com/complete/saml/`.  This is
      the "SAML ACS url" in SAML terminology.

      If you're
      [hosting multiple organizations](../production/multiple-organizations.html#authentication),
      you need to use `SOCIAL_AUTH_SUBDOMAIN`.  For example,
      if `SOCIAL_AUTH_SUBDOMAIN="auth"` and `EXTERNAL_HOST=zulip.example.com`,
      this should be `https://auth.zulip.example.com/complete/saml/`.

2. Tell Zulip how to connect to your SAML provider(s) by filling
   out the section of `/etc/zulip/settings.py` on your Zulip server
   with the heading "SAML Authentication".
   * You will need to update `SOCIAL_AUTH_SAML_ORG_INFO` with your
     organization name (`displayname` may appear in the IdP's
     authentication flow; `name` won't be displayed to humans).
   * Fill out `SOCIAL_AUTH_SAML_ENABLED_IDPS` with data provided by
     your identity provider.  You may find [the python-social-auth
     SAML
     docs](https://python-social-auth.readthedocs.io/en/latest/backends/saml.html)
     helpful.  You'll need to obtain several values from your IdP's
     metadata and enter them on the right-hand side of this
     Python dictionary:
     1. Set the outer `idp_name` key to be an identifier for your IdP,
        e.g. `testshib` or `okta`.  This field appears in URLs for
        parts of your Zulip server's SAML authentication flow.
     2. The IdP should provide the `url` and `entity_id` values.
     3. Save the `x509cert` value to a file; you'll use it in the
        instructions below.
     4. The values needed in the `attr_` fields are often configurable
        in your IdP's interface when setting up SAML authentication
        (referred to as "Attribute Statements" with Okta, or
        "Attribute Mapping" with GSuite).  You'll want to connect
        these so that Zulip gets the email address (used as a unique
        user ID) and name for the user.
     5. The `display_name` and `display_icon` fields are used to
        display the login/registration buttons for the IdP.

3. Install the certificate(s) required for SAML authentication.  You
    will definitely need the public certificate of your IdP.  Some IdP
    providers also support the Zulip server (Service Provider) having
    a certificate used for encryption and signing.  We detail these
    steps as optional below, because they aren't required for basic
    setup, and some IdPs like Okta don't fully support Service
    Provider certificates.  You should install them as follows:

    1. On your Zulip server, `mkdir -p /etc/zulip/saml/idps/`
    2. Put the IDP public certificate in `/etc/zulip/saml/idps/{idp_name}.crt`
    3. (Optional) Put the Zulip server public certificate in `/etc/zulip/saml/zulip-cert.crt`
    4. (Optional) Put the Zulip server private key in `/etc/zulip/saml/zulip-private-key.key`
    5. Set the proper permissions on these files and directories:

    ```
    chown -R zulip.zulip /etc/zulip/saml/
    find /etc/zulip/saml/ -type f -exec chmod 644 -- {} +
    chmod 640 /etc/zulip/saml/zulip-private-key.key
    ```

4. (Optional) If you configured the optional public and private server
   certificates above, you can enable the additional setting
   `"authnRequestsSigned": True` in `SOCIAL_AUTH_SAML_SECURITY_CONFIG`
   to have the SAMLRequests the server will be issuing to the IdP
   signed using those certificates.  Additionally, if the IdP supports
   it, you can upload the public certificate to enable encryption of
   assertions in the SAMLResponses the IdP will send about
   authenticated users.

5. Enable the `zproject.backends.SAMLAuthBackend` auth backend, in
`AUTHENTICATION_BACKENDS` in `/etc/zulip/settings.py`.

6. [Restart the Zulip server](../production/settings.md) to ensure
your settings changes take effect.  The Zulip login page should now
have a button for SAML authentication that you can use to log in or
create an account (including when creating a new organization).

7. If the configuration was successful, the server's metadata can be
found at `https://yourzulipdomain.example.com/saml/metadata.xml`. You
can use this for verifying your configuration or provide it to your
IdP.

[saml-help-center]: https://zulip.com/help/saml-authentication

### IdP-initiated SSO

The above configuration is sufficient for Service Provider initialized
SSO, i.e. you can visit the Zulip webapp and click "Sign in with
{IdP}" and it'll correctly start the authentication flow.  If you are
not hosting multiple organizations, with Zulip 3.0+, the above
configuration is also sufficient for Identity Provider initiated SSO,
i.e. clicking a "Sign in to Zulip" button on the IdP's website can
correctly authenticate the user to Zulip.

If you're hosting multiple organizations and thus using the
`SOCIAL_AUTH_SUBDOMAIN` setting, you'll need to configure a custom
`RelayState` in your IdP of the form `{"subdomain":
"yourzuliporganization"}` to let Zulip know which organization to
authenticate the user to when they visit your SSO URL from the IdP.
(If the organization is on the root domain, use the empty string:
`{"subdomain": ""}`.).

```eval_rst
.. _ldap:
```

### Restricting access to specific organizations

If you're hosting multiple Zulip organizations, you can restrict which
organizations can use a given IdP by setting `limit_to_subdomains`.
For example, `limit_to_subdomains = ["", "engineering"]` would
restrict an IdP the root domain and the `engineering` subdomain.

You can achieve the same goal with a SAML attribute; just declare
which attribute using `attr_org_membership` in the IdP configuration.
For the root subdomain, `www` in the list will work, or any other of
`settings.ROOT_SUBDOMAIN_ALIASES`.

For example, with `attr_org_membership` set to `member`, a user with
the following attribute in their `AttributeStatement` will have access
to the root and `engineering` subdomains:

```
<saml2:Attribute Name="member" NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:unspecified">
  <saml2:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="xs:string">
    www
  </saml2:AttributeValue>
  <saml2:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="xs:string">
    engineering
  </saml2:AttributeValue>
</saml2:Attribute>
```

## LDAP (including Active Directory)

Zulip supports retrieving information about users via LDAP, and
optionally using LDAP as an authentication mechanism.

In either configuration, you will need to do the following:

1. These instructions assume you have an installed Zulip server and
   are logged into a shell there.  You can have created an
   organization already using EmailAuthBackend, or plan to create the
   organization using LDAP authentication.

1. Tell Zulip how to connect to your LDAP server:
   * Fill out the section of your `/etc/zulip/settings.py` headed "LDAP
     integration, part 1: Connecting to the LDAP server".
   * If a password is required, put it in
     `/etc/zulip/zulip-secrets.conf` by setting
     `auth_ldap_bind_password`.  For example: `auth_ldap_bind_password
     = abcd1234`.

1. Decide how you want to map the information in your LDAP database to
   users' account data in Zulip.  For each Zulip user, two closely
   related concepts are:
   * their **email address**.  Zulip needs this in order to send, for
     example, a notification when they're offline and another user
     sends a PM.
   * their **Zulip username**.  This means the name the user types into the
     Zulip login form.  You might choose for this to be the user's
     email address (`sam@example.com`), or look like a traditional
     "username" (`sam`), or be something else entirely, depending on
     your environment.

   Either or both of these might be an attribute of the user records
   in your LDAP database.

1. Tell Zulip how to map the user information in your LDAP database to
   the form it needs for authentication.  There are three supported
   ways to set up the username and/or email mapping:

   (A) Using email addresses as Zulip usernames, if LDAP has each
      user's email address:
      * Make `AUTH_LDAP_USER_SEARCH` a query by email address.
      * Set `AUTH_LDAP_REVERSE_EMAIL_SEARCH` to the same query with
        `%(email)s` rather than `%(user)s` as the search parameter.
      * Set `AUTH_LDAP_USERNAME_ATTR` to the name of the LDAP
        attribute for the user's LDAP username in the search result
        for `AUTH_LDAP_REVERSE_EMAIL_SEARCH`.

   (B) Using LDAP usernames as Zulip usernames, with email addresses
      formed consistently like `sam` -> `sam@example.com`:
      * Set `AUTH_LDAP_USER_SEARCH` to query by LDAP username
      * Set `LDAP_APPEND_DOMAIN = "example.com"`.

   (C) Using LDAP usernames as Zulip usernames, with email addresses
      taken from some other attribute in LDAP (for example, `mail`):
      * Set `AUTH_LDAP_USER_SEARCH` to query by LDAP username
      * Set `LDAP_EMAIL_ATTR = "mail"`.
      * Set `AUTH_LDAP_REVERSE_EMAIL_SEARCH` to a query that will find
        an LDAP user given their email address (i.e. a search by
        `LDAP_EMAIL_ATTR`).  For example:
        ```
        AUTH_LDAP_REVERSE_EMAIL_SEARCH = LDAPSearch("ou=users,dc=example,dc=com",
                                                    ldap.SCOPE_SUBTREE, "(mail=%(email)s)")
        ```
      * Set `AUTH_LDAP_USERNAME_ATTR` to the name of the LDAP
        attribute for the user's LDAP username in that search result.

You can quickly test whether your configuration works by running:

```
/home/zulip/deployments/current/manage.py query_ldap username
```

from the root of your Zulip installation.  If your configuration is
working, that will output the full name for your user (and that user's
email address, if it isn't the same as the "Zulip username").

**Active Directory**: Most Active Directory installations will use one
of the following configurations:

* To access by Active Directory username:
    ```
    AUTH_LDAP_USER_SEARCH = LDAPSearch("ou=users,dc=example,dc=com",
                                       ldap.SCOPE_SUBTREE, "(sAMAccountName=%(user)s)")
    AUTH_LDAP_REVERSE_EMAIL_SEARCH = LDAPSearch("ou=users,dc=example,dc=com",
                                       ldap.SCOPE_SUBTREE, "(mail=%(email)s)")
    AUTH_LDAP_USERNAME_ATTR = "sAMAccountName"
    ```

* To access by Active Directory email address:
    ```
    AUTH_LDAP_USER_SEARCH = LDAPSearch("ou=users,dc=example,dc=com",
                                       ldap.SCOPE_SUBTREE, "(mail=%(user)s)")
    AUTH_LDAP_REVERSE_EMAIL_SEARCH = LDAPSearch("ou=users,dc=example,dc=com",
                                                ldap.SCOPE_SUBTREE, "(mail=%(email)s)")
    AUTH_LDAP_USERNAME_ATTR = "mail"
    ```

**If you are using LDAP for authentication**: you will need to enable
the `zproject.backends.ZulipLDAPAuthBackend` auth backend, in
`AUTHENTICATION_BACKENDS` in `/etc/zulip/settings.py`.  After doing so
(and as always [restarting the Zulip server](settings.md) to ensure
your settings changes take effect), you should be able to log into
Zulip by entering your email address and LDAP password on the Zulip
login form.

You may also want to configure Zulip's settings for [inviting new
users](https://zulip.com/help/invite-new-users).  If LDAP is the
only enabled authentication method, the main use case for Zulip's
invitation feature is selecting the initial streams for invited users
(invited users will still need to use their LDAP password to create an
account).

### Synchronizing data

Zulip can automatically synchronize data declared in
`AUTH_LDAP_USER_ATTR_MAP` from LDAP into Zulip, via the following
management command:

```
/home/zulip/deployments/current/manage.py sync_ldap_user_data
```

This will sync the fields declared in `AUTH_LDAP_USER_ATTR_MAP` for
all of your users.

We recommend running this command in a **regular cron job**, to pick
up changes made on your LDAP server.

All of these data synchronization options have the same model:
* New users will be populated automatically with the
  name/avatar/etc. from LDAP (as configured) on account creation.
* The `manage.py sync_ldap_user_data` cron job will automatically
  update existing users with any changes that were made in LDAP.
* You can easily test your configuration using `manage.py query_ldap`.
  Once you're happy with the configuration, remember to restart the
  Zulip server with
  `/home/zulip/deployments/current/scripts/restart-server` so that
  your configuration changes take effect.

When using this feature, you may also want to
[prevent users from changing their display name in the Zulip UI][restrict-name-changes],
since any such changes would be automatically overwritten on the sync
run of `manage.py sync_ldap_user_data`.

[restrict-name-changes]: https://zulip.com/help/restrict-name-and-email-changes

#### Synchronizing avatars

Starting with Zulip 2.0, Zulip supports syncing LDAP / Active
Directory profile pictures (usually available in the `thumbnailPhoto`
or `jpegPhoto` attribute in LDAP) by configuring the `avatar` key in
`AUTH_LDAP_USER_ATTR_MAP`.

#### Synchronizing custom profile fields

Starting with Zulip 2.0, Zulip supports syncing
[custom profile fields][custom-profile-fields] from LDAP / Active
Directory.  To configure this, you first need to
[configure some custom profile fields][custom-profile-fields] for your
Zulip organization.  Then, define a mapping from the fields you'd like
to sync from LDAP to the corresponding LDAP attributes.  For example,
if you have a custom profile field `LinkedIn Profile` and the
corresponding LDAP attribute is `linkedinProfile` then you just need
to add `'custom_profile_field__linkedin_profile': 'linkedinProfile'`
to the `AUTH_LDAP_USER_ATTR_MAP`.

[custom-profile-fields]: https://zulip.com/help/add-custom-profile-fields

#### Automatically deactivating users with Active Directory

Starting with Zulip 2.0, Zulip supports synchronizing the
disabled/deactivated status of users from Active Directory.  You can
configure this by uncommenting the sample line `"userAccountControl":
"userAccountControl",` in `AUTH_LDAP_USER_ATTR_MAP` (and restarting
the Zulip server).  Zulip will then treat users that are disabled via
the "Disable Account" feature in Active Directory as deactivated in
Zulip.

Users disabled in active directory will be immediately unable to log in
to Zulip, since Zulip queries the LDAP/Active Directory server on
every login attempt.  The user will be fully deactivated the next time
your `manage.py sync_ldap_user_data` cron job runs (at which point
they will be forcefully logged out from all active browser sessions,
appear as deactivated in the Zulip UI, etc.).

This feature works by checking for the `ACCOUNTDISABLE` flag on the
`userAccountControl` field in Active Directory.  See
[this handy resource](https://jackstromberg.com/2013/01/useraccountcontrol-attributeflag-values/)
for details on the various `userAccountControl` flags.

#### Deactivating non-matching users

Starting with Zulip 2.0, Zulip supports automatically deactivating
users if they are not found by the `AUTH_LDAP_USER_SEARCH` query
(either because the user is no longer in LDAP/Active Directory, or
because the user no longer matches the query).  This feature is
enabled by default if LDAP is the only authentication backend
configured on the Zulip server.  Otherwise, you can enable this
feature by setting `LDAP_DEACTIVATE_NON_MATCHING_USERS` to `True` in
`/etc/zulip/settings.py`.  Nonmatching users will be fully deactivated
the next time your `manage.py sync_ldap_user_data` cron job runs.

#### Other fields

Other fields you may want to sync from LDAP include:

* Boolean flags; `is_realm_admin` (the organization's administrator
  permission) is the main one.  You can use the
  [AUTH_LDAP_USER_FLAGS_BY_GROUP][django-auth-booleans] feature of
  `django-auth-ldap` to configure a group to get this permissions.
  (We don't recommend using this flags feature for managing
  `is_active` because deactivating a user this way would not disable
  any active sessions the user might have; see the above discussion of
  automatic deactivation for how to do that properly).
* String fields like `default_language` (e.g. `en`) or `timezone`, if
  you have that data in the right format in your LDAP database.
* [Coming soon][custom-profile-fields-ldap]: Support for syncing
  [custom profile fields](https://zulip.com/help/add-custom-profile-fields)
  from your LDAP database.

You can look at the [full list of fields][models-py] in the Zulip user
model; search for `class UserProfile`, but the above should cover all
the fields that would be useful to sync from your LDAP databases.

[models-py]: https://github.com/zulip/zulip/blob/master/zerver/models.py
[django-auth-booleans]: https://django-auth-ldap.readthedocs.io/en/latest/users.html#easy-attributes
[custom-profile-fields-ldap]: https://github.com/zulip/zulip/issues/10976

### Multiple LDAP searches

To do the union of multiple LDAP searches, use `LDAPSearchUnion`.  For example:
```
AUTH_LDAP_USER_SEARCH = LDAPSearchUnion(
    LDAPSearch("ou=users,dc=example,dc=com", ldap.SCOPE_SUBTREE, "(uid=%(user)s)"),
    LDAPSearch("ou=otherusers,dc=example,dc=com", ldap.SCOPE_SUBTREE, "(uid=%(user)s)"),
)
```

### Restricting access to an LDAP group

You can restrict access to your Zulip server to a set of LDAP groups
using the `AUTH_LDAP_REQUIRE_GROUP` and `AUTH_LDAP_DENY_GROUP`
settings in `/etc/zulip/settings.py`.  See the
[upstream django-auth-ldap documentation][upstream-ldap-groups] for
details.

[upstream-ldap-groups]: https://django-auth-ldap.readthedocs.io/en/latest/groups.html#limiting-access

### Troubleshooting

Most issues with LDAP authentication are caused by misconfigurations of
the user and email search settings.  Some things you can try to get to
the bottom of the problem:

* Review the instructions for the LDAP configuration type you're
  using: (A), (B) or (C) (described above), and that you have
  configured all of the required settings documented in the
  instructions for that configuration type.
* Use the `manage.py query_ldap` tool to verify your configuration.
  The output of the command will usually indicate the cause of any
  configuration problem.  For the LDAP integration to work, this
  command should be able to successfully fetch a complete, correct set
  of data for the queried user.
* You can find LDAP-specific logs in `/var/log/zulip/ldap.log`. If
  you're asking for help with your setup, please provide logs from
  this file (feel free to anonymize any email addresses to
  `username@example.com`) in your report.

## Apache-based SSO with `REMOTE_USER`

If you have any existing SSO solution where a preferred way to deploy
it (a) runs inside Apache, and (b) sets the `REMOTE_USER` environment
variable, then the `ZulipRemoteUserBackend` method provides you with a
straightforward way to deploy that SSO solution with Zulip.

### Setup instructions for Apache-based SSO

1. In `/etc/zulip/settings.py`, configure two settings:

   * `AUTHENTICATION_BACKENDS`: `'zproject.backends.ZulipRemoteUserBackend'`,
     and no other entries.

   * `SSO_APPEND_DOMAIN`: see documentation in `settings.py`.

   Make sure that you've restarted the Zulip server since making this
   configuration change.

2. Edit `/etc/zulip/zulip.conf` and change the `puppet_classes` line to read:

   ```
   puppet_classes = zulip::profile::voyager, zulip::apache_sso
   ```

3. As root, run `/home/zulip/deployments/current/scripts/zulip-puppet-apply`
   to install our SSO integration.

4. To configure our SSO integration, edit a copy of
   `/etc/apache2/sites-available/zulip-sso.example`, saving the result
   as `/etc/apache2/sites-available/zulip-sso.conf`.  The example sets
   up HTTP basic auth, with an `htpasswd` file; you'll want to replace
   that with configuration for your SSO solution to authenticate the
   user and set `REMOTE_USER`.

   For testing, you may want to move ahead with the rest of the setup
   using the `htpasswd` example configuration and demonstrate that
   working end-to-end, before returning later to configure your SSO
   solution.  You can do that with the following steps:
   ```
   /home/zulip/deployments/current/scripts/restart-server
   cd /etc/apache2/sites-available/
   cp zulip-sso.example zulip-sso.conf
   htpasswd -c /home/zulip/zpasswd username@example.com # prompts for a password
   ```

5. Run `a2ensite zulip-sso` to enable the SSO integration within Apache.

6. Run `service apache2 reload` to use your new configuration.  If
   Apache isn't already running, you may need to run `service apache2
   start` instead.

Now you should be able to visit your Zulip server in a browser (e.g.,
at `https://zulip.example.com/`) and log in via the SSO solution.

### Troubleshooting Apache-based SSO

Most issues with this setup tend to be subtle issues with the
hostname/DNS side of the configuration.  Suggestions for how to
improve this SSO setup documentation are very welcome!

* For example, common issues have to do with `/etc/hosts` not mapping
  `settings.EXTERNAL_HOST` to the Apache listening on
  `127.0.0.1`/`localhost`.

* While debugging, it can often help to temporarily change the Apache
  config in `/etc/apache2/sites-available/zulip-sso` to listen on all
  interfaces rather than just `127.0.0.1`.

* While debugging, it can also be helpful to change `proxy_pass` in
  `/etc/nginx/zulip-include/app.d/external-sso.conf` to point to a
  more explicit URL, possibly not over HTTPS.

* The following log files can be helpful when debugging this setup:

   * `/var/log/zulip/{errors.log,server.log}` (the usual places)
   * `/var/log/nginx/access.log` (nginx access logs)
   * `/var/log/apache2/zulip_auth_access.log` (from the
     `zulip-sso.conf` Apache config file; you may want to change
     `LogLevel` in that file to "debug" to make this more verbose)

### Life of an Apache-based SSO login attempt

Here's a summary of how the Apache `REMOTE_USER` SSO system works,
assuming you're using the example configuration with HTTP basic auth.
This summary should help with understanding what's going on as you try
to debug.

* Since you've configured `/etc/zulip/settings.py` to only define the
  `zproject.backends.ZulipRemoteUserBackend`,
  `zproject/computed_settings.py` configures `/accounts/login/sso/` as
  `HOME_NOT_LOGGED_IN`.  This makes `https://zulip.example.com/`
  (a.k.a. the homepage for the main Zulip Django app running behind
  nginx) redirect to `/accounts/login/sso/` for a user that isn't
  logged in.

* nginx proxies requests to `/accounts/login/sso/` to an Apache
  instance listening on `localhost:8888`, via the config in
  `/etc/nginx/zulip-include/app.d/external-sso.conf` (using the
  upstream `localhost_sso`, defined in `/etc/nginx/zulip-include/upstreams`).

* The Apache `zulip-sso` site which you've enabled listens on
  `localhost:8888` and (in the example config) presents the `htpasswd`
  dialogue.  (In a real configuration, it takes the user through
  whatever more complex interaction your SSO solution performs.)  The
  user provides correct login information, and the request reaches a
  second Zulip Django app instance, running behind Apache, with
  `REMOTE_USER` set.  That request is served by
  `zerver.views.remote_user_sso`, which just checks the `REMOTE_USER`
  variable and either logs the user in or, if they don't have an
  account already, registers them.  The login sets a cookie.

* After succeeding, that redirects the user back to `/` on port 443.
  This request is sent by nginx to the main Zulip Django app, which
  sees the cookie, treats them as logged in, and proceeds to serve
  them the main app page normally.

## Sign in with Apple

Zulip supports using the web flow for Sign in with Apple on
self-hosted servers.  To do so, you'll need to do the following:

1. Visit [the Apple Developer site][apple-developer] and [Create a
Services ID.][apple-create-services-id]. When prompted for a "Return
URL", enter `https://zulip.example.com/complete/apple/` (using the
domain for your server).

1. Create a [Sign in with Apple private key][apple-create-private-key].

1. Store the resulting private key at
   `/etc/zulip/apple-auth-key.p8`.  Be sure to set
   permissions correctly:

   ```
   chown zulip:zulip /etc/zulip/apple-auth-key.p8
   chmod 640 /etc/zulip/apple-auth-key.p8
   ```

1. Configure Apple authentication in `/etc/zulip/settings.py`:
   * `SOCIAL_AUTH_APPLE_TEAM`: Your Team ID from Apple, which is a
     string like "A1B2C3D4E5".
   * `SOCIAL_AUTH_APPLE_SERVICES_ID`: The Services ID you created in
     step 1, which might look like "com.example.services".
   * `SOCIAL_AUTH_APPLE_APP_ID`: The App ID, or Bundle ID, of your
     app that you used in step 1 to configure your Services ID.
     This might look like "com.example.app".
   * `SOCIAL_AUTH_APPLE_KEY`: Despite the name this is not a key, but
     rather the Key ID of the key you created in step 2.  This looks
     like "F6G7H8I9J0".
   * `AUTHENTICATION_BACKENDS`: Uncomment (or add) a line like
     `'zproject.backends.AppleAuthBackend',` to enable Apple auth
     using the created configuration.

1. Register with Apple the email addresses or domains your Zulip
   server sends email to users from.  For instructions and background,
   see the "Email Relay Service" subsection of
   [this page][apple-get-started].  For details on what email
   addresses Zulip sends from, see our
   [outgoing email documentation][outgoing-email].

[apple-create-services-id]: https://help.apple.com/developer-account/?lang=en#/dev1c0e25352
[apple-developer]: https://developer.apple.com/account/resources/
[apple-create-private-key]: https://help.apple.com/developer-account/?lang=en#/dev77c875b7e
[apple-get-started]: https://developer.apple.com/sign-in-with-apple/get-started/
[outgoing-email]: ../production/email.md

## Adding more authentication backends

Adding an integration with any of the more than 100 authentication
providers supported by [python-social-auth][python-social-auth] (e.g.,
Facebook, Twitter, etc.) is easy to do if you're willing to write a
bit of code, and pull requests to add new backends are welcome.

For example, the
[Azure Active Directory integration](https://github.com/zulip/zulip/commit/49dbd85a8985b12666087f9ea36acb6f7da0aa4f)
was about 30 lines of code, plus some documentation and an
[automatically generated migration][schema-migrations].  We also have
helpful developer documentation on
[testing auth backends](../development/authentication.md).

[schema-migrations]: ../subsystems/schema-migrations.md
[python-social-auth]: https://python-social-auth.readthedocs.io/en/latest/

## Development only

The `DevAuthBackend` method is used only in development, to allow
passwordless login as any user in a development environment.  It's
mentioned on this page only for completeness.
