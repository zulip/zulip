# Securing your Zulip server

This page offers practical information on how to secure your Zulip server. For a
deeper understanding of the security model, take a look at Zulip's [security
overview](https://zulip.com/security/).

Here are some best practices for keeping your Zulip server secure:

1. [Limit shell access to a small set of trusted individuals.](#1-limit-shell-access-to-a-small-set-of-trusted-individuals)
2. [Consider requiring authentication with single sign-on (SSO).](#2-consider-requiring-authentication-with-single-sign-on-sso)
3. [Teach users how to protect their account.](#3-teach-users-how-to-protect-their-account)
4. [Become familiar with Zulip's access management model.](#4-become-familiar-with-zulips-access-management-model)
5. [Understand security for user-uploaded content and user-generated requests.](#5-understand-security-for-user-uploaded-content-and-user-generated-requests)
6. [Understand Zulip's rate-limiting system.](#6-understand-zulips-rate-limiting-system)

If you believe you've identified a security issue, please report it to Zulip's
security team at [security@zulip.com](mailto:security@zulip.com) as soon as
possible, so that we can address it and make a responsible disclosure.

## 1. Limit shell access to a small set of trusted individuals.

Anyone with root access to a Zulip application server or Zulip database server,
or with access to the `zulip` user on a Zulip application server, has _complete
control over the Zulip installation_ and all of its data (so they can read
messages, modify history, etc.). This means that _only trusted individuals_
should have shell access to your Zulip server.

## 2. Consider requiring authentication with single sign-on (SSO).

The preferred way to log in to Zulip is using a single sign-on (SSO)
solution like Google authentication, LDAP, or similar, but Zulip
also supports password authentication. See [the authentication
methods documentation](authentication-methods.md) for
details on Zulip's available authentication methods.

## 3. Teach users how to protect their account.

Every Zulip user has an API key, which can be used to do essentially everything
that users can do when they're logged in. Make sure users know to immediately
[reset their API key and password](https://zulip.com/help/protect-your-account)
if their credentials are compromised (e.g., their cell phone is lost or stolen).

## 4. Become familiar with Zulip's access management model.

Zulip's help center offers a detailed overview of Zulip's permissions management
system. Reading the following guides will give you a good starting point:

- [Channel types and permissions](https://zulip.com/help/channel-permissions)
- [User roles](https://zulip.com/help/user-roles)
- [User groups](https://zulip.com/help/user-groups)
- [Restrict message editing and deletion](https://zulip.com/help/restrict-message-editing-and-deletion)
- [Bots overview](https://zulip.com/help/bots-overview)

## 5. Understand security for user-uploaded content and user-generated requests.

- Zulip supports user-uploaded files. Ideally they should be hosted
  from a separate domain from the main Zulip server to protect against
  various same-domain attacks (e.g., zulip-user-content.example.com).

  We support two ways of hosting them: the basic `LOCAL_UPLOADS_DIR`
  file storage backend, where they are stored in a directory on the
  Zulip server's filesystem, and the S3 backend, where the files are
  stored in Amazon S3. It would not be difficult to add additional
  supported backends should there be a need; see
  `zerver/lib/upload.py` for the full interface.

  For both backends, the URLs used to access uploaded files are long,
  random strings, providing one layer of security against unauthorized
  users accessing files uploaded in Zulip (an authorized user would
  need to share the URL with an unauthorized user in order for the
  file to be accessed by the unauthorized user. Of course, any
  such authorized user could have just downloaded and sent the file
  instead of the URL, so this is arguably pretty good protection.)

  However, to help protect against accidental sharing of URLs to
  restricted files (e.g., by forwarding a missed-message email or leaks
  involving the Referer header), every access to an uploaded file has
  access control verified (confirming that the browser is logged into
  a Zulip account that has received the uploaded file in question).

- Zulip supports using the [go-camo][go-camo] image proxy to proxy content like
  inline image previews, that can be inserted into the Zulip message feed by
  other users. This ensures that clients do not make requests to external
  servers to fetch images, improving privacy.

- By default, Zulip will provide image previews inline in the body of
  messages when a message contains a link to an image. You can
  control this using the `INLINE_IMAGE_PREVIEW` setting.

- Zulip may make outgoing HTTP connections to other servers in a
  number of cases:

  - Outgoing webhook bots (creation of which can be restricted)
  - Inline image previews in messages (enabled by default, but can be disabled)
  - Inline webpage previews and embeds (must be configured to be enabled)
  - Twitter message previews (must be configured to be enabled)
  - BigBlueButton and Zoom API requests (must be configured to be enabled)
  - Mobile push notifications (must be configured to be enabled)

- Notably, these first 3 features give end users (limited) control to cause
  the Zulip server to make HTTP requests on their behalf. Because of this,
  Zulip routes all outgoing HTTP requests [through
  Smokescreen][smokescreen-setup] to ensure that Zulip cannot be
  used to execute [SSRF attacks][ssrf] against other systems on an
  internal corporate network. The default Smokescreen configuration
  denies access to all non-public IP addresses, including 127.0.0.1.

  The Camo image server does not, by default, route its traffic
  through Smokescreen, since Camo includes logic to deny access to
  private subnets; this can be [overridden][proxy.enable_for_camo].

[go-camo]: https://github.com/cactus/go-camo
[ssrf]: https://owasp.org/www-community/attacks/Server_Side_Request_Forgery
[smokescreen-setup]: deployment.md#customizing-the-outgoing-http-proxy
[proxy.enable_for_camo]: system-configuration.md#enable_for_camo

## 6. Understand Zulip's rate-limiting system.

Zulip has built-in rate limiting of login attempts, all access to the
API, as well as certain other types of actions that may be involved in
abuse. For example, the email confirmation flow, by its nature, needs
to allow sending an email to an email address that isn't associated
with an existing Zulip account. Limiting the ability of users to
trigger such emails helps prevent bad actors from damaging the spam
reputation of a Zulip server by sending confirmation emails to random
email addresses.

The default rate limiting rules for a Zulip server will change as we improve
the product. A server administrator can browse the current rules using
`/home/zulip/deployments/current/scripts/get-django-setting
RATE_LIMITING_RULES`; or with comments by reading
`DEFAULT_RATE_LIMITING_RULES` in `zproject/default_settings.py`.

Server administrators can tweak rate limiting in the following ways in
`/etc/zulip/settings.py`:

- The `RATE_LIMITING` setting can be set to `False` to completely
  disable all rate-limiting.
- The `RATE_LIMITING_RULES` setting can be used to override specific
  rules. See the comment in the file for more specific details on how
  to do it. After changing the setting, we recommend using
  `/home/zulip/deployments/current/scripts/get-django-setting
RATE_LIMITING_RULES` to verify your changes. You can then restart
  the Zulip server with `scripts/restart-server` to have the new
  configuration take effect.
- The `RATE_LIMIT_TOR_TOGETHER` setting can be set to `True` to group all
  known exit nodes of [TOR](https://www.torproject.org/) together for purposes
  of IP address limiting. Since traffic from a client using TOR is distributed
  across its exit nodes, without enabling this setting, TOR can otherwise be
  used to avoid IP-based rate limiting. The updated list of TOR exit nodes
  is refetched once an hour.
- If a user runs into the rate limit for login attempts, a server
  administrator can clear this state using the
  `manage.py reset_authentication_attempt_count`
  [management command][management-commands].

See also our [API documentation on rate limiting][rate-limit-api].

[management-commands]: ../production/management-commands.md
[rate-limit-api]: https://zulip.com/api/rest-error-handling#rate-limit-exceeded
