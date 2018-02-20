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
  [the authentication methods documentation](../production/authentication-methods.html)
  for details on Zulip's available authentication methods.

### Passwords

Zulip stores user passwords using the standard PBKDF2 algorithm.

When the user is choosing a password, Zulip checks the password's
strength using the popular [zxcvbn][zxcvbn] library.  Weak passwords
are rejected, and strong passwords encouraged.  The minimum password
strength allowed is controlled by two settings in
`/etc/zulip/settings.py`:

* `PASSWORD_MIN_LENGTH`: The minimum acceptable length, in characters.
  Shorter passwords are rejected even if they pass the `zxcvbn` test
  controlled by `PASSWORD_MIN_GUESSES`.

* `PASSWORD_MIN_GUESSES`: The minimum acceptable strength of the
  password, in terms of the estimated number of passwords an attacker
  is likely to guess before trying this one. If the user attempts to
  set a password that `zxcvbn` estimates to be guessable in less than
  `PASSWORD_MIN_GUESSES`, then Zulip rejects the password.

  By default, `PASSWORD_MIN_GUESSES` is 10000. This provides
  significant protection against online attacks, while limiting the
  burden imposed on users choosing a password.

  <!--- Why 10000?  See /production/password-strength.md. -->

  Estimating the guessability of a password is a complex problem and
  impossible to efficiently do perfectly. For background or when
  considering an alternate value for this setting, the article
  ["Passwords and the Evolution of Imperfect Authentication"][BHOS15]
  is recommended.  The [2016 zxcvbn paper][zxcvbn-paper] adds useful
  information about the performance of zxcvbn, and [a large 2012 study
  of Yahoo users][Bon12] is informative about the strength of the
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
[BHOS15]: http://www.cl.cam.ac.uk/~fms27/papers/2015-BonneauHerOorSta-passwords.pdf
[zxcvbn-paper]: https://www.usenix.org/system/files/conference/usenixsecurity16/sec16_paper_wheeler.pdf
[Bon12]: http://ieeexplore.ieee.org/document/6234435/

## Messages and History

* Zulip message content is rendered using a specialized Markdown
  parser which escapes content to protect against cross-site scripting
  attacks.

* Zulip supports both public streams and private ("invite-only")
  streams.  Any Zulip user can join any public stream in the realm,
  and can view the complete message history of any public stream
  without joining the stream.

* A private ("invite-only") stream is hidden from users who are not
  subscribed to the stream.
  * Users who are not members of a private stream cannot read messages
    on the stream, send messages to the stream, or join the stream,
    even if they are a Zulip organization administrator.
  * Any member of a private stream can add other users to the stream.
    This is the only way that one can join a private stream (even
    organization administrators cannot join a private stream without
    being added by an existing member).
  * When a new user joins a private stream, they can see future
    messages sent to the stream, but they do not receive access to the
    stream's message history.
  * Organization administrators can do some basic management of
    private streams that they are not subscribed to: Changing the
    stream name and description, viewing the current subscribers, and
    removing subscribers.

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
  receive to another service.  Zulip stores the edit history of
  messages, but it may or may not be available to clients, depending
  on an organization-level setting.

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
  like the Jabber, IRC, and Zephyr mirrors).  They also have the
  ability to see the names of all streams (including private streams).

  They can only be created on the command line (with `manage.py
  knight --permission=api_super_user`).

## User-uploaded content

* Zulip supports user-uploaded files.  Ideally they should be hosted
  from a separate domain from the main Zulip server to protect against
  various same-domain attacks (e.g. zulip-user-content.example.com).

  We support two ways of hosting them: the basic `LOCAL_UPLOADS_DIR`
  file storage backend, where they are stored in a directory on the
  Zulip server's filesystem, and the S3 backend, where the files are
  stored in Amazon S3.  It would not be difficult to add additional
  supported backends should there be a need; see
  `zerver/lib/upload.py` for the full interface.

  For both backends, the URLs used to access uploaded files are long,
  random strings, providing one layer of security against unauthorized
  users accessing files uploaded in Zulip (an authorized user would
  need to share the URL with an unauthorized user in order for the
  file to be accessed by the unauthorized user; and of course, any
  such authorized user could have just downloaded and sent the file
  instead of the URL, so this is arguably the best protection
  possible).  However, to help protect against consequences accidental
  sharing of URLs to restricted files (e.g. by forwarding a
  missed-message email or leaks involving the Referer header), we
  provide additional layers of protection in both backends as well.

  In the Zulip S3 backend, the random URLs to access files that are
  presented to users don't actually host the content.  Instead, the S3
  backend verifies that the user has a valid Zulip session in the
  relevant realm (and that has access to a Zulip message linking to
  the file), and if so, then redirects the browser to a temporary S3
  URL for the file that expires a short time later.  In this way,
  possessing a URL to a secret file in Zulip does not provide
  unauthorized users with access to that file.

  We have a similar protection for the `LOCAL_UPLOADS_DIR` backend,
  that is currently only available in Ubuntu Xenial (this is the one
  place in Zulip where behavior is currently different between Ubuntu
  Trusty and Ubuntu Xenial).  On Ubuntu Xenial, every access to an
  uploaded file has access control verified verified (confirming that
  the browser is logged into a Zulip account that has received the
  uploaded file in question).

  On Ubuntu Trusty, because the older version of `nginx` available
  there doesn't have proper Unicode support for the `X-Accel-Redirect`
  feature, the `LOCAL_UPLOADS_DIR` backend only has the single layer
  of security described at the beginning of this section (long,
  randomly generated secret URLs).  This could be fixed with further
  engineering, but given the upcoming end-of-life of Ubuntu Trusty, we
  have no plans to do that further work.

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
