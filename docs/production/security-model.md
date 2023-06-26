# Security model

This section attempts to document the Zulip security model. It likely
does not cover every issue; if there are details you're curious about,
please feel free to ask questions in [#production
help](https://chat.zulip.org/#narrow/stream/31-production-help) on the
[Zulip community server](https://zulip.com/development-community/) (or if you
think you've found a security bug, please report it to
security@zulip.com so we can do a responsible security
announcement).

## Secure your Zulip server like your email server

- It's reasonable to think about security for a Zulip server like you
  do security for a team email server -- only trusted individuals
  within an organization should have shell access to the server.

  In particular, anyone with root access to a Zulip application server
  or Zulip database server, or with access to the `zulip` user on a
  Zulip application server, has complete control over the Zulip
  installation and all of its data (so they can read messages, modify
  history, etc.). It would be difficult or impossible to avoid this,
  because the server needs access to the data to support features
  expected of a group chat system like the ability to search the
  entire message history, and thus someone with control over the
  server has access to that data as well.

## Encryption and authentication

- Traffic between clients (web, desktop and mobile) and the Zulip
  server is encrypted using HTTPS. By default, all Zulip services
  talk to each other either via a localhost connection or using an
  encrypted SSL connection.

- Zulip requires CSRF tokens in all interactions with the web API to
  prevent CSRF attacks.

- The preferred way to log in to Zulip is using a single sign-on (SSO)
  solution like Google authentication, LDAP, or similar, but Zulip
  also supports password authentication. See [the authentication
  methods documentation](authentication-methods.md) for
  details on Zulip's available authentication methods.

### Passwords

Zulip stores user passwords using the standard Argon2 and PBKDF2
algorithms. Argon2 is used for all new and changed passwords as of
Zulip Server 1.6.0, but legacy PBKDF2 passwords that were last changed
before the 1.6.0 upgrade are still supported.

When the user is choosing a password, Zulip checks the password's
strength using the popular [zxcvbn][zxcvbn] library. Weak passwords
are rejected, and strong passwords encouraged. The minimum password
strength allowed is controlled by two settings in
`/etc/zulip/settings.py`:

- `PASSWORD_MIN_LENGTH`: The minimum acceptable length, in characters.
  Shorter passwords are rejected even if they pass the `zxcvbn` test
  controlled by `PASSWORD_MIN_GUESSES`.

- `PASSWORD_MIN_GUESSES`: The minimum acceptable strength of the
  password, in terms of the estimated number of passwords an attacker
  is likely to guess before trying this one. If the user attempts to
  set a password that `zxcvbn` estimates to be guessable in less than
  `PASSWORD_MIN_GUESSES`, then Zulip rejects the password.

  By default, `PASSWORD_MIN_GUESSES` is 10000. This provides
  significant protection against online attacks, while limiting the
  burden imposed on users choosing a password. See
  [password strength](password-strength.md) for an extended
  discussion on how we chose this value.

  Estimating the guessability of a password is a complex problem and
  impossible to efficiently do perfectly. For background or when
  considering an alternate value for this setting, the article
  ["Passwords and the Evolution of Imperfect Authentication"][bhos15]
  is recommended. The [2016 zxcvbn paper][zxcvbn-paper] adds useful
  information about the performance of zxcvbn, and [a large 2012 study
  of Yahoo users][bon12] is informative about the strength of the
  passwords users choose.

<!---
  If the BHOS15 link ever goes dead: it's reference 30 of the zxcvbn
  paper, aka https://dl.acm.org/citation.cfm?id=2699390 , in the
  _Communications of the ACM_ aka CACM.  (But the ACM has it paywalled.)
  .
  Hooray for USENIX and IEEE: the other papers' canonical links are
  not paywalled.  The Yahoo study is reference 5 in BHOS15.
-->

[zxcvbn]: https://github.com/dropbox/zxcvbn
[bhos15]: http://www.cl.cam.ac.uk/~fms27/papers/2015-BonneauHerOorSta-passwords.pdf
[zxcvbn-paper]: https://www.usenix.org/system/files/conference/usenixsecurity16/sec16_paper_wheeler.pdf
[bon12]: http://ieeexplore.ieee.org/document/6234435/

## Messages and history

- Zulip message content is rendered using a specialized Markdown
  parser which escapes content to protect against cross-site scripting
  attacks.

- Zulip supports both public streams and private streams.

  - Any non-guest user can join any public stream in the organization,
    and can view the complete message history of any public stream
    without joining the stream. Guests can only access streams that
    another user adds them to.

  - Organization owners and administrators can see and modify most
    aspects of a private stream, including the membership and
    estimated traffic. Owners and administrators generally cannot see
    messages sent to private streams or do things that would
    indirectly give them access to those messages, like adding members
    or changing the stream privacy settings.

  - Non-admins cannot easily see which private streams exist, or interact
    with them in any way until they are added. Given a stream name, they can
    figure out whether a stream with that name exists, but cannot see any
    other details about the stream.

  - See [Stream permissions](https://zulip.com/help/stream-permissions) for more details.

- Zulip supports editing the content and topics of messages that have
  already been sent. As a general philosophy, our policies provide
  hard limits on the ways in which message content can be changed or
  undone. In contrast, our policies around message topics favor
  usefulness (e.g. for conversational organization) over faithfulness
  to the original. In all configurations:

  - Message content can only ever be modified by the original author.

  - Any message visible to an organization owner or administrator can
    be deleted at any time by that administrator.

  - See
    [Restrict message editing and deletion](https://zulip.com/help/configure-message-editing-and-deletion)
    for more details.

## Users and bots

- There are several types of users in a Zulip organization: organization
  owners, organization administrators, members (normal users), guests,
  and bots.

- Owners and administrators have the ability to deactivate and
  reactivate other human and bot users, archive streams, add/remove
  administrator privileges, as well as change configuration for the
  organization.

  Being an organization administrator does not generally provide the ability
  to read other users' direct messages or messages sent to private
  streams to which the administrator is not subscribed. There are two
  exceptions:

  - Organization owners may get access to direct messages via some types of
    [data export](https://zulip.com/help/export-your-organization).

  - Administrators can change the ownership of a bot. If a bot is subscribed
    to a private stream, then an administrator can indirectly get access to
    stream messages by taking control of the bot, though the access will be
    limited to what the bot can do. (E.g. incoming webhook bots cannot read
    messages.)

- Every Zulip user has an API key, available on the settings page.
  This API key can be used to do essentially everything the user can
  do; for that reason, users should keep their API key safe. Users
  can rotate their own API key if it is accidentally compromised.

- To properly remove a user's access to a Zulip team, it does not
  suffice to change their password or deactivate their account in a
  single sign-on (SSO) system, since neither of those prevents
  authenticating with the user's API key or those of bots the user has
  created. Instead, you should [deactivate the user's
  account](https://zulip.com/help/deactivate-or-reactivate-a-user) via
  Zulip's "Organization settings" interface.

- The Zulip mobile apps authenticate to the server by sending the
  user's password and retrieving the user's API key; the apps then use
  the API key to authenticate all future interactions with the site.
  Thus, if a user's phone is lost, in addition to changing passwords,
  you should rotate the user's Zulip API key.

- Guest users are like Members, but they do not have automatic access
  to public streams.

- Zulip supports several kinds of bots with different capabilities.

  - Incoming webhook bots can only send messages into Zulip.
  - Outgoing webhook bots and Generic bots can essentially do anything a
    non-administrator user can, with a few exceptions (e.g. a bot cannot
    log in to the web application, register for mobile push
    notifications, or create other bots).
  - Bots with the `can_forge_sender` permission can send messages that appear to have been sent by
    another user. They also have the ability to see the names of all
    streams, including private streams. This is important for implementing
    integrations like the Jabber, IRC, and Zephyr mirrors.

    These bots cannot be created by Zulip users, including
    organization owners. They can only be created on the command
    line (via `manage.py change_user_role can_forge_sender`).

## User-uploaded content and user-generated requests

- Zulip supports user-uploaded files. Ideally they should be hosted
  from a separate domain from the main Zulip server to protect against
  various same-domain attacks (e.g. zulip-user-content.example.com).

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
  restricted files (e.g. by forwarding a missed-message email or leaks
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
[proxy.enable_for_camo]: deployment.md#enable_for_camo

## Rate limiting

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

## Final notes and security response

If you find some aspect of Zulip that seems inconsistent with this
security model, please report it to security@zulip.com so that we can
investigate and coordinate an appropriate security release if needed.

Zulip security announcements will be sent to
zulip-announce@googlegroups.com, so you should subscribe if you are
running Zulip in production.
