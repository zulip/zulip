# Security Model

This section attempts to document the Zulip security model.  Since
this is new documentation, it likely does not cover every issue; if
there are details you're curious about, please feel free to ask
questions on the Zulip development mailing list (or if you think
you've found a security bug, please report it to
zulip-security@googlegroups.com so we can do a responsible security
announcement).

## Secure your Zulip server like your email server

* It's reasonable to think about security for a Zulip server like you
  do security for a team email server -- only trusted administrators
  within an organization should have shell access to the server.

  In particular, anyone with root access to a Zulip application server
  or Zulip database server, or with access to the `zulip` user on a
  Zulip application server, has complete control over the Zulip
  installation and all of its data (so they can read messages, modify
  history, etc.).  It would be difficult or impossible to avoid this,
  because the server needs access to the data to support features
  expected of a group chat system like the ability to search the
  entire message history, and thus someone with control over the
  server has access to that data as well.

## Encryption and Authentication

* Traffic between clients (web, desktop and mobile) and the Zulip is
  encrypted using HTTPS.  By default, all Zulip services talk to each
  other either via a localhost connection or using an encrypted SSL
  connection.

* Zulip requires CSRF tokens in all interactions with the web API to
  prevent CSRF attacks.

* The preferred way to login to Zulip is using an SSO solution like
  Google Auth, LDAP, or similar, but Zulip also supports password
  authentication.  See
  [the authentication methods documentation](prod-authentication-methods.html)
  for details on Zulip's available authentication methods.

### Passwords

Zulip stores user passwords using the standard PBKDF2 algorithm.
Password strength is checked and weak passwords are visually
discouraged using the popular
[zxcvbn](https://github.com/dropbox/zxcvbn) library.  The minimum
password strength allowed is controlled by two settings in
`/etc/zulip/settings.py`; `PASSWORD_MIN_LENGTH` and
`PASSWORD_MIN_ZXCVBN_QUALITY`.  The former is self-explanatory; we
will explain the latter.

Password strength estimation is a complicated topic that we can't go
into great detail on here; we recommend reading the zxvcbn website for
details if you are not familiar with password strength analysis.

In Zulip's configuration, a password has quality `X` if zxcvbn
estimates that it would take `e^(X * 22)` seconds to crack the
password with a specific attack scenario.  The scenario Zulip uses is
one where an the attacker breaks into the Zulip server and steals the
hashed passwords; in that case, with a slow hash, the attacker would
be able to make roughly 10,000 attempts per second.  E.g. a password
with quality 0.5 (the default), it would take an attacker about 16
hours to crack such a password in this sort of offline attack.

Another important attack scenario is the online attacks (i.e. an
attacker sending tons of login requests guessing different passwords
to a Zulip server over the web).  Those attacks are much slower (more
like 10/second without rate limiting), and you should estimate the
time to guess a password as correspondingly longer.

As a server administrators, you must balance the security risks
associated with attackers guessing weak passwords against the
usability challenges associated with requiring strong passwords in
your organization.

## Messages and History

* Zulip message content is rendered using a specialized Markdown
  parser which escapes content to protect against cross-site scripting
  attacks.

* Zulip supports both public streams and private ("invite-only")
  streams.  Any Zulip user can join any public stream in the realm,
  and can view the complete message history of any public stream
  without joining the stream.

* A private ("invite-only") stream is hidden from users who are not
  subscribed to the stream.  Users who are not members of a private
  stream cannot read messages on the stream, send messages to the
  stream, or join the stream, even if they are a Zulip realm
  administrator.  Users can join private streams only when they are
  invited.  However, any member of a private stream can invite other
  users to the stream.  When a new user joins a private stream, they
  can see future messages sent to the stream, but they do not receive
  access to the stream's message history.

* Zulip supports editing the content and topics of messages that have
  already been sent. As a general philosophy, our policies provide
  hard limits on the ways in which message content can be changed or
  undone. In contrast, our policies around message topics favor
  usefulness (e.g. for conversational organization) over faithfulness
  to the original.

  The message editing policy can be configured on the /#organization
  page. There are three configurations provided out of the box: (i)
  users cannot edit messages at all, (ii) users can edit any message
  they have sent, and (iii) users can edit the content of any message
  they have sent in the last N minutes, and the topic of any message
  they have sent. In (ii) and (iii), topic edits can also be
  propagated to other messages with the same original topic, even if
  those messages were sent by other users. The default setting is
  (iii), with N = 10.

  In addition, and regardless of the configuration above, messages
  with no topic can always be edited to have a topic, by anyone in the
  organization, and the topic of any message can also always be edited
  by a realm administrator.

  Also note that while edited messages are synced immediately to open
  browser windows, editing messages is not a safe way to redact secret
  content (e.g. a password) shared unintentionally. Other users may
  have seen and saved the content of the original message, or have an
  integration (e.g. push notifications) forwarding all messages they
  receive to another service. Zulip also stores and sends to clients
  the content of every historical version of a message.

## Users and Bots

* There are three types of users in a Zulip realm: Administrators,
  normal users, and bots.  Administrators have the ability to
  deactivate and reactivate other human and bot users, delete streams,
  add/remove administrator privileges, as well as change configuration
  for the overall realm (e.g. whether an invitation is required to
  join the realm).  Being a Zulip administrator does not provide the
  ability to interact with other users' private messages or the
  messages sent to private streams to which the administrator is not
  subscribed.  However, a Zulip administrator subscribed to a stream
  can toggle whether that stream is public or private.  Also, Zulip
  realm administrators have administrative access to the API keys of
  all bots in the realm, so a Zulip administrator may be able to
  access messages sent to private streams that have bots subscribed,
  by using the bot's credentials.

  In the future, Zulip's security model may change to allow realm
  administrators to access private messages (e.g. to support auditing
  functionality).

* Every Zulip user has an API key, available on the settings page.
  This API key can be used to do essentially everything the user can
  do; for that reason, users should keep their API key safe.  Users
  can rotate their own API key if it is accidentally compromised.

* To properly remove a user's access to a Zulip team, it does not
  suffice to change their password or deactivate their account in the
  SSO system, since neither of those prevents authenticating with the
  user's API key or those of bots the user has created.  Instead, you
  should deactivate the user's account in the "Organization settings"
  interface (`/#organization`); this will automatically also
  deactivate any bots the user had created.

* The Zulip mobile apps authenticate to the server by sending the
  user's password and retrieving the user's API key; the apps then use
  the API key to authenticate all future interactions with the site.
  Thus, if a user's phone is lost, in addition to changing passwords,
  you should rotate the user's Zulip API key.

* Zulip bots are used for integrations.  A Zulip bot can do everything
  a normal user in the realm can do including reading other, with a
  few exceptions (e.g. a bot cannot login to the web application or
  create other bots).  In particular, with the API key for a Zulip
  bot, one can read any message sent to a public stream in that bot's
  realm.  A likely future feature for Zulip is [limited bots that can
  only send messages](https://github.com/zulip/zulip/issues/373).

* Certain Zulip bots can be marked as "API super users"; these special
  bots have the ability to send messages that appear to have been sent
  by another user (an important feature for implementing integrations
  like the Jabber, IRC, and Zephyr mirrors).

## User-uploaded content

* Zulip supports user-uploaded files; ideally they should be hosted
  from a separate domain from the main Zulip server to protect against
  various same-domain attacks (e.g. zulip-user-content.example.com)
  using the S3 integration.

  The URLs of user-uploaded files are secret; if you are using the
  "local file upload" integration, anyone with the URL of an uploaded
  file can access the file.  This means the local uploads integration
  is vulnerable to a subtle attack where if a user clicks on a link in
  a secret .PDF or .HTML file that had been uploaded to Zulip, access
  to the file might be leaked to the other server via the Referrer
  header (see [the "Uploads world readable" issue on
  GitHub](https://github.com/zulip/zulip/issues/320)).

  The Zulip S3 file upload integration is relatively safe against that
  attack, because the URLs of files presented to users don't host the
  content.  Instead, the S3 integration checks the user has a valid
  Zulip session in the relevant realm, and if so then redirects the
  browser to a one-time S3 URL that expires a short time later.
  Keeping the URL secret is still important to avoid other users in
  the Zulip realm from being able to access the file.

* Zulip supports using the Camo image proxy to proxy content like
  inline image previews that can be inserted into the Zulip message
  feed by other users over HTTPS.

* By default, Zulip will provide image previews inline in the body of
  messages when a message contains a link to an image.  You can
  control this using the `INLINE_IMAGE_PREVIEW` setting.

## Final notes and security response

If you find some aspect of Zulip that seems inconsistent with this
security model, please report it to zulip-security@googlegroups.com so
that we can investigate and coordinate an appropriate security release
if needed.

Zulip security announcements will be sent to
zulip-announce@googlegroups.com, so you should subscribe if you are
running Zulip in production.
