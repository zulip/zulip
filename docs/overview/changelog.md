# Version history

This page contains the release history for the Zulip server. See also the
[Zulip release lifecycle](../overview/release-lifecycle.md).

## Zulip 9.x series

### 9.0 -- unreleased

This section is an incomplete draft of the release notes for the next
major release, and is only updated occasionally. See the [commit
log][commit-log] for an up-to-date list of all changes.

#### Upgrade notes for 9.0

- This release introduces a new [Zulip updates](https://zulip.com/help/configure-automated-notices#zulip-update-announcements) feature, which
  announces significant product changes and new features via automated
  messages to a configurable stream. Generally, these announcements will
  be sent automatically when upgrading to the new release. However, when
  you first upgrade to the 9.x series, they will be sent with a delay
  (explained in an automated direct message to organization administrators)
  to give time to potentially reconfigure which stream to use. You can
  override the delay by running `./manage.py send_zulip_update_announcements --skip-delay`
  once you've done any necessary configuration updates.

## Zulip Server 8.x series

### Zulip Server 8.3

_Released 2024-03-19_

- **CVE-2024-27286:** Incorrectly preserved access when moving messages between
  streams.
- Added beta support for the upcoming Ubuntu 24.04 release.
- Added new DM search options to the compliant export tool.
- Added a helpful error page for installations trying to access “plan
  management” when they had not configured the mobile push notifications service
  yet.
- Added a
  [local-disk database backup](../production/export-and-import.md#streaming-backups-to-local-disk)
  option.
- Added the ability to store
  [incremental database backups](../production/system-configuration.md#backups_incremental).
- Improved performance of bulk-moving messages between streams by ~2x.
- Streamlined documentation for the Zulip server installer.
- Fixed the “Topics are required for this organization” pop-up incorrectly
  closing on some keypresses.
- Fixed the analytics cron job leaking its lock if unexpectedly interrupted
  (e.g. by a reboot).
- Fixed sorting by expiration date in the “Invites” settings panel.
- Fixed the gear menu staying open after clicking on “plan management”.
- Fixed a small visual issue with bot icons in the left sidebar DM section.
- Fixed installation with an existent but empty `zulip` database.
- Backported various developer tooling improvements.
- Upgraded dependencies.
- Updated translations, including new translations for Gujarati and Greek.

### Zulip Server 8.2

_Released 2024-02-16_

- Fixed an error reporting bug that caused an email to be sent to the
  server administrator each time that the server had a failed attempt
  to send a mobile push notification. This bug could cause a lot of
  error emails on servers that are registered with the [Mobile Push
  Notification Service][mobile-push], but are not signed up for a plan
  that includes access to this service, or not [uploading basic
  metadata][mobile-push-metadata] required to verify eligibility for
  free access to the service.
- Fixed several scroll position bugs encountered when entering a
  conversation view, most importantly when opening a direct message
  conversation.
- Fixed a minor bug in the organization settings UI.
- Improved rate-limiting logic to avoid errors when loading the app for some users.
- Adjusted memory usage configuration to reduce memory usage to avoid
  OOM kills on systems with close to 4GiB of RAM, and require less
  tuning for larger systems.
- Upgraded dependencies.
- Updated translations.

### Zulip Server 8.1

_Released 2024-01-24_

- CVE-2024-21630: Zulip version 8.0 and its betas had a bug affecting
  an unlikely permissions configuration where some user roles had
  permission to create reusable invitation links to join the
  organization, but lacked the permission to subscribe other users to
  streams. A user with such a role could incorrectly create an
  invitation link that subscribes new users to streams. This
  vulnerability is similar to CVE-2023-32677, but applies to multi-use
  invitations, not single-user invites.
- Fixed a fault-tolerance bug, where failing outgoing email
  authentication could cause other queue workers to not progress
  properly on low-memory Zulip servers.
- Added support for using PostgreSQL 16 as the database. See the
  PostgreSQL upgrade documentation if you’re interested in upgrading
  an existing server to newer Postgres.
- Added support for explicitly deactivating a mobile push
  notifications registration.
- Added support for a new class of custom authentication hook.
- Improved the workflow for sending password reset emails to users
  imported from another chat app.
- Improved the file uploads integration to be compatible with S3
  alternatives that use a different URL addressing style.
- Improved the Terms of Service/Privacy Policy settings if no policies
  sidebar is configured.
- Fixed a bug preventing the incoming email integration from
  mentioning groups that everyone is allowed to mention.
- Fixed the data import tool crashing when processing delivered
  scheduled messages.
- Fixed buggy tooltips in the push notifications column of
  notification settings.
- Fixed minor UI bugs with the user group settings panel.
- Fixed minor UI bugs with the new compose box buttons.
- Fixed minor UI bugs with limiting guest user access to other users.
- Fixed incorrect alert words color in the dark theme.
- Fixed a few subtle bugs with the Zulip plan management login flow.
- Fixed a live-update bug involving user statuses enabled via the API.
- Fixed a configuration problem preventing the logrotate service from
  starting.
- Fixed a layout bug for the mobile help center navbar area affecting
  some servers.
- Fixed Slack data import tool corner cases involving shared users.
- Fixed mentions being incorrectly converted to silent mentions in DMs
  with bot users.
- Fixed an unexploitable HTML injection bug in the typeahead for
  configuring custom code playgrounds.
- Improved in-app documentation for following topics.
- Backported several documentation improvements.

### Zulip Server 8.0

_Released 2023-12-15_

#### Highlights

- New Inbox view shows all unread messages in a conveniently
  browsable experience, similar to the mobile home screen. It is an
  option for the user's home view.
- Added support for following a topic, with configurable notification
  settings for followed topics and flexible configuration options to
  automatically follow topics when sending a message or otherwise
  interacting with it, or when mentioned. New `Shift + N` keyboard
  shortcut navigates to the next unread followed topic.
- Added support for limiting user list access for guests.
- New @topic mentions support mentioning only users who have
  participated in a topic by sending a message or emoji reaction.
- Typing notifications now support streams with 100 or fewer
  subscribers.
- Clicking on a message in search views now directly takes the user to
  the target message, instead of starting a reply, since it's rare one
  wants to reply without full context.
- The left sidebar now allows collapsing the global views for users
  who want more space for streams and conversations.
- Added new unread count display style setting, controlling in which
  streams to display a numeric unread count or a simple dot unread
  indicator. Defaults to numeric counts in normal streams, but a dot
  indicator in muted streams.
- Added support for creating voice calls.
- Major visual design improvements in the message feed, search
  area/navbar, and left sidebar. The gear menu was replaced with three
  new redesigned menus: A help menu, a personal/avatar menu, and a
  more focused gear menu.
- Added thumbnails and lightbox player support for video links and
  video files uploaded directly in Zulip. Previously, Zulip only
  supported this for videos hosted by third-party platforms that
  provide an embedded player, like YouTube and Vimeo.
- The compose area was redesigned, with new formatting buttons for
  most message formatting features, including polls. Improved pasting
  URLs with text selected. Topic typeahead now indicates whether one
  would be creating a new topic, and user typeahead now shows pronouns
  if a pronoun custom profile field is configured.

#### Full feature changelog

- Redesigned the "invite users" modal to be more user-friendly.
- Redesigned file upload, including a cancel button, better
  drag-and-drop support, better message-edit handling, and many bug
  fixes.
- Redesigned managing groups to use a side-by-side panel UI similar to
  stream settings. This is an important step towards our upcoming
  support for groups-based permissions.
- Redesigned how very tall messages are condensed.
- Redesigned email confirmation page.
- Redesigned various settings panels to remove clutter and simplify
  the user experience.
- The LDAP integration now supports syncing user groups.
- The SCIM integration now supports syncing user roles.
- The recent view now indicates the date range it is displaying, and
  supports fetching more conversations and sorting by unread count.
- Added support for printing a message feed as a lightweight
  conversation export experience.
- Added support for muting bot users.
- Added support for multi-character emoji sequences and other modern
  emoji; Twitter emojiset now backfills missing emoji from the Google
  emojiset just like the Google blobs emojiset does.
- Added user profile tab for administrators to edit the profile.
- Added support for subscribing users in user profile streams tab.
- Added new permissions setting for who can create reusable invitation
  links.
- Added new setting for whether guest users should be displayed with
  "(guest)" appended to their name to highlight their status.
- Added new setting to configure the Jitsi server URL to use.
- Added new settings warnings for making a stream private that one is
  not subscribed to, and for archiving a stream used for automated
  notifications.
- Added new wizard for creating incoming webhook integration URLs.
- Added bulk-delete UI for drafts.
- Added new API endpoint for sending a test push notification, to
  support an upcoming mobile feature. Realms now have a UUID sent to
  the push notifications service to simplify migrating via
  export/import into a different server.
- Display settings was renamed to Preferences.
- "Default view" was renamed to "home view".
- The manage streams UI has a cleaner design for changing
  subscriptions, can now directly manage default streams, and has
  a cleaner UI for managing notification settings.
- Linkifiers and code playgrounds now use RFC 6570 compliant URL
  templates to specify the target URL.
- Linkifiers are now processed in a defined, editable order.
- Scheduled messages are now displayed when viewing the conversation
  where they will be sent.
- Message edit history has a Shift+H keyboard shortuct and is now
  accessed via the mouse exclusively by clicking on EDITED/MOVED
  notices, simplifying the main message actions popover.
- Users can now delete messages sent by bots that they control as
  though they had sent the message themselves.
- Simplified and clarified recipient bar inline topic editing.
- The compose/edit interfaces now disable formatting buttons in
  preview mode.
- The organization creation form now explicitly asks the user to
  choose a default language for the organization.
- Improved design for /todo widgets.
- Improved defaults for which portion of a topic to move when moving
  messages.
- Improved semantics and explanations of reactivating previously
  deactivated bot users.
- Improved over 100 help center articles, adding mobile documentation
  for many common workflows and a new indexing system for message
  formatting documentation.
- Improved onboarding hints for steps one might want to take before
  inviting users.
- Improved display for uploaded images that had been deleted.
- Improved content and styling for many tooltips across the web
  application, including several new "Copied!" tooltips.
- Improved configurability of outgoing email sender names.
- Improved the ability of a self-hosted server to tell the mobile apps
  whether mobile push notifications are working.
- Improved integrations: CircleCI, Gitea, GitHub, GitLab,
  Sentry. Regenerated integration screenshots to show the current
  visual design.
- Webhook integrations now return a 200 success status code when
  processing requests that match the format for an integration but
  where the specific event type is not implemented.
- New /health health check endpoint designed for reverse proxies in
  front of the Zulip server.
- Rewrote all popovers, fixing many bugs involving positioning, mobile
  web UI, and keyboard navigation.
- Rewrote message feed layout using CSS grid, fixing many subtle
  layout bugs.
- Fixed dozens of rare exceptions in the web application.
- Fixed email notifications incorrectly containing extra context
  messages when subscribed to email notifications for a stream.
- Fixed several longstanding performance issues both in the web
  application and the server, and a small memory leak.
- Fixed several subtle bugs in error reporting internals.
- Fixed multiple subtle deadlocks in database locking code.
- Fixed several subtle bugs in the compose box.
- Fixed LaTeX being misrendered in desktop, email and push notifications.
- Fixed several subtle internationalization bugs.
- Fixed multiple subtle linkification bugs.
- Fixed many subtle bugs in settings.
- Fixed nginx configuration for HTTP/3.
- Added explicit SAML configuration documentation for Authentik.
- Clarified dozens of ambiguous details and minor errors in API
  documentation.
- Reworked the main database indexes used to fetch messages.
- Reimplemented the internals of the audit logging system.
- Many structural improvements to the permission settings internals
  working towards permission settings being group-based.
- Many structural improvements to the web app codebase. About 25% of
  the web codebase is now TypeScript, most of the legacy Bootstrap
  code has been deleted, and most import cycles have been cut.
- Added new request parsing framework based on Pydantic 2.
- Upgraded many dependencies.

#### Upgrade notes for 8.0

- Installations using the [Mobile Push Notifications
  Service][mobile-push] now regularly upload [basic
  metadata][mobile-push-metadata] about the organizations hosted by
  the installation to the Mobile Push Notifications
  Service. Previously, basic metadata was uploaded only when uploading
  usage statistics was also enabled via the `SUBMIT_USAGE_STATISTICS`
  setting.
- This release contains several expensive migrations, most notably
  `0472_add_message_realm_id_indexes.py`,
  `0485_alter_usermessage_flags_and_add_index.py`, and
  `0486_clear_old_data_for_unused_usermessage_flags.py`. Migration
  `0486`, in particular, cleans up stale that should only be present
  on Zulip servers that were originally installed with Zulip 1.3.x or
  older. If your server has millions of messages, plan for the
  migrations in this release to take 15 minutes or more to complete.
- Minor: User group names starting with `@`, `role:`, `user:`, and
  various certain other special patterns are now forbidden. In the
  unlikely event that existing user groups have names matching these
  patterns, they will be automatically renamed on upgrade.
- The behavior of the `AUTH_LDAP_ADVANCED_REALM_ACCESS_CONTROL` has
  subtly changed. Previously, using this setting at all would block
  LDAP authentication in organizations that are configured to use LDAP
  authentication but not explicitly configured with advanced access
  controls. This behavior was removed to simplify hosting multiple
  organizations with different LDAP configuration preferences.

[mobile-push-metadata]: ../production/mobile-push-notifications.md#uploading-usage-statistics

## Zulip Server 7.x series

### Zulip Server 7.5

_Released 2023-11-16_

- CVE-2023-47642: Invalid metadata access for formerly subscribed streams.
  It was discovered by the Zulip development team that active users who had
  previously been subscribed to a stream incorrectly continued being able to use
  the Zulip API to access metadata for that stream. As a result, users who had
  been removed from a stream, but still had an account in the organization,
  could still view metadata for that stream (including the stream name,
  description, settings, and an email address used to send emails into the
  stream via the incoming email integration). This potentially allowed users to
  see changes to a stream’s metadata after they had lost access to the stream.
  This bug was present in all Zulip releases prior to Zulip Server 7.5.
- Fixed a bug where [backups](../production/export-and-import.md#backups) might
  be written using `postgresql-client-16`, which could not be straightforwardly
  restored into a Zulip instance, as the format is not backwards-compatible, and
  Zulip does not yet support PostgreSQL 16.
- Renamed the `reactivate_stream` management command to `unarchive_stream`, to
  match terminology in the app, and [documented
  it](https://zulip.com/help/archive-a-stream#unarchiving-archived-streams).
- Fixed a regression, introduced in 6.0, where users created via the API or LDAP
  would have English set as their language, ignoring the configured realm
  default.
- Improved [documentation on `AUTH_LDAP_ADVANCED_REALM_ACCESS_CONTROL`](../production/authentication-methods.md#restricting-ldap-user-access-to-specific-organizations).
- Improved error messages for subdomains being reserved versus being in use.
- Upgraded Python dependencies.

### Zulip Server 7.4

_Released 2023-09-15_

- CVE-2023-4863: Upgrade vulnerable `libwebp` dependency.
- Fixed a left sidebar layout bug affecting languages like Russian
  with very long translations of certain menu items.
- Fixed a bug in the reverse proxy misconfiguration warnings
  introduced in 7.2.
- Fixed a bug causing some exception report emails generated by the
  Zulip server to be unpleasantly verbose.
- Fixed the compose area “Enter sends” configuration incorrectly
  advertising “Enter” instead of “Return” on macOS systems.
- Fixed a CSS bug in the password reset form introduced in 7.3.
- Improved troubleshooting guide discussion of restarting services.
- Upgrade dependencies.

### Zulip Server 7.3

_Released 2023-08-25_

- CVE-2023-32678: Users who used to be subscribed to a private stream, and have
  since been removed from it, retained the ability to edit messages/topics and
  delete messages that they used to have access to, if other relevant
  organization permissions allowed these actions. For example, a user may have
  still been able to edit or delete their old messages they had posted in such a
  private stream.
- Fixed a bug, introduced in Zulip Server 7.0, which would cause uploaded files
  attached to some messages to be mistakenly deleted after some, but not all,
  messages linking to the uploaded file were deleted by the user. See our
  [blog post](https://blog.zulip.com/2023/08/25/uploaded-file-data-loss-incident/) for more details.
- Fixed a bug, introduced in Zulip Server 7.2 in the
  [operating system upgrade process](../production/upgrade.md#upgrading-the-operating-system),
  which would cause errors of the form
  `venv was not set up for this Python version`.
- Fixed a bug, introduced in Zulip Server 7.2, when the
  [email gateway](../production/email-gateway.md)
  was used in conjunction with a
  [reverse proxy](../production/reverse-proxies.md).
- Improved the performance of
  [resolving](https://zulip.com/help/resolve-a-topic) or
  [moving](https://zulip.com/help/move-content-to-another-topic) long topics.
- Fixed bad rendering of stream links in
  [stream descriptions](https://zulip.com/help/change-the-stream-description).
- Fixed broken and misaligned images in Zulip welcome emails.
- Fixed YouTube video previews to be ordered in the order they are linked, not
  reverse order.
- Upgraded Python requirements.
- Updated puppet dependencies.
- Improved the [Sentry integration](https://zulip.com/integrations/doc/sentry),
  including making the “Test plugin” button in Sentry work properly.
- Reduced memory usage by replacing a custom error reporting handler with the
  default Django implementation. This will result in a slight change in the
  format of server exception emails. Such emails should be rare in most
  self-hosted systems; installations with a large amount of server exception
  volume should be using the
  [Sentry integration](../subsystems/logging.md#sentry-error-logging).
- Updated the
  [data export tool](../production/export-and-import.md#data-export)
  to handle bots created in very early versions of Zulip Server.
- Fixed a bug with the
  [data export tool](../production/export-and-import.md#data-export)
  and deleted users in group DMs.
- Added a `./manage.py reactivate-stream` command to reactivate archived
  streams.
- Fixed links in the documentation to
  [Modify Zulip](../production/modify.md)
  and
  [Upgrade Zulip](../production/upgrade.md)
  pages.
- Linked the documentation on how to
  [host multiple Zulip](../production/multiple-organizations.md)
  organizations on one server.
- Fixed missing images in documentation for the
  [“XKCD” bot](https://zulip.com/integrations/doc/xkcd).
- Fixed “Back to login page” button alignment in the desktop app.
- Added a reference to
  [PostgreSQL upgrades](../production/upgrade.md#upgrading-postgresql)
  in the
  [release upgrade](../production/upgrade.md#upgrading-to-a-release)
  section.
- Clarified that PostgreSQL versions must match in
  "[Restoring backups](../production/export-and-import.md#restoring-backups)"
  section, and explain how to do that.
- Reformatted Changelog.

### Zulip Server 7.2

_Released 2023-07-05_

- Started logging a more accurate, detailed, and actionable error messages when
  [common reverse proxy misconfigurations][proxies] are detected.

- Improved [reverse proxy documentation][proxies] to clarify that trust of
  `X-Forwarded-Proto` is also necessary.

- Removed [reverse proxy][proxies] nginx configuration files when the
  [`loadbalancer.ips`](../production/system-configuration.md#ips)
  setting has been unset.
- Improved error-handling of scheduled emails, so they cannot attempt infinite
  deliveries of a message with no recipients.
- Fixed a bug with the
  [PGroonga integration](../subsystems/full-text-search.md#multi-language-full-text-search)
  that would cause the PostgreSQL server to crash when a search was run.
- Fixed a bug that would cause some messages not to be marked as read.
- Fixed a bug that still showed file-upload banners after re-opening the compose
  box.
- Fixed a bug that prevented file uploads with very unusual file names.
- Adjusted the bot icon to make it more visible on the light theme.
- Fixed minor rendering issues on the “press enter to send” indicator.
- Fixed the scrollbar behavior on the stream settings page.
- Improved error reporting when a Slack token fails to validate during
  [import](https://zulip.com/help/import-from-slack#export-your-slack-data),
  such as a token having too few permissions.
- Added support for IPv6
  [nameservers in the nginx configuration](../production/system-configuration.md#nameserver).
- Updated translations.

[proxies]: ../production/reverse-proxies.md#configuring-zulip-to-trust-proxies

### Zulip Server 7.1

_Released 2023-06-13_

- Added checks to check that Zulip is being installed on a
  [supported CPU and OS architecture](../production/requirements.md).
- Improved error-handling around the
  [`upgrade-postgresql`](../production/upgrade.md#upgrading-postgresql)
  tool.
- Fixed a couple bugs in database migrations as part of the upgrade that could
  cause the upgrade to fail to complete.
- Fixed a bug where
  [scheduled messages](https://zulip.com/help/schedule-a-message) with `@all`
  would fail to send.
- Fixed a bug which would sometimes cause the `j` and `k` keys to not be able to
  be typed in the compose box.
- Fixed anonymous access to the “download” link on images in
  [public-access streams](https://zulip.com/help/public-access-option).
- Changed the default DNS resolver in nginx’s configuration to match the
  system’s; this fixes deployments which use the
  [S3 storage backend](../production/upload-backends.md)
  and did not run `systemd-resolved`, like Docker and some versions of Debian.
- Updated several pieces of documentation.
- Updated translations, including new translations for Luri (Bakhtiari),
  Brazilian Portuguese, and Tagalog.

### Zulip Server 7.0

_Released 2023-05-31_

#### Highlights

- Many significant visual changes as part of Zulip's ongoing redesign
  project, including message feed headers, background color, mention
  colors, dates and times, compose box banners, icons, and
  tooltips. Many further improvements are planned for future releases.
- Added support for unmuting a topic in a muted stream, previously the
  4th most upvoted GitHub issue.
- Redesigned the permissions settings for message editing, topic
  editing, and moving topics to have a cleaner model.
- New compose box features: Scheduling a message to be sent later, a
  nicer stream picker, and the ability to switch between stream and
  private messages.
- Numerous improvements to the Help Center, including documentation
  for how to complete many common tasks in the Zulip mobile apps.
- Redesigned the interface and permissions model for moving topics to
  be independent from message content editing, providing a cleaner
  experience and better configurability.
- Renamed "Private messages" to "Direct messages" across the user
  interface, including search operators. We expect further API changes
  to be integrated gradually over coming releases due to backwards
  compatibility considerations.
- Added a new personal privacy setting for to what extent the user's
  email address should be shared with other users in the organization;
  previously this was solely controlled by organization
  administrators. This is presented to the user during account
  creation, including for users imported from other chat products.
- Added support for the upcoming Debian 12 release.

#### Full feature changelog

- Added full support for using JWT authentication to integrate Zulip
  with another application.
- Added support for SAML Single-Logout initiated by the Zulip server
  (SP-initiated Single Logout).
- Added new stream setting controlling which users can remove other
  subscribers from the stream.
- Added new setting to control when messages are marked as read when
  scrolling.
- Added notification bot messages when another user adds you to or
  removes you from a user group.
- Added additional confirmation dialogs for actions deserving caution,
  including marking all messages as read, removing the last user from a
  private stream, and disabling all notifications for direct messages.
- Added support for Postgres 15, and removed support for Postgres 11.
- Added new `z` keyboard shortcut to view a message in context.
- Added new `=` keyboard shortcut to upvote an existing emoji reaction.
- Changed the `s` keyboard shortcut to be a toggle, replacing the
  previous model that required both `s` and `S` keyboard shortcuts.
- Clarified automated notifications when moving and resolving topics.
- New webhook integrations: Rundeck.
- Reworked linkifiers to use URL templates for the URL patterns.
- Improved left sidebar to show more topics within the current stream,
  and more private message conversations, especially when many are
  unread.
- Reworked the internals of the main message feed scrollbar, fixing
  several longstanding bugs.
- Improved many interaction details in the settings subsystem,
  including how files are uploaded, hover behaviors, etc.
- Improved the logged out experience to suggest logging in to see more
  streams in the left sidebar.
- Improved many subtle details of compose box autocomplete, file
  uploads, and error handling. Browser undo now works more
  consistently in the compose box.
- Improved subscriber management in stream settings to support sorting
  users and seeing their user cards after a click.
- Improved previously unspecified behavior when multiple overlapping
  linkifiers applied to syntax within a message.
- Improved subject lines for email notifications in topics that have
  been resolved so that email clients will thread them with the
  pre-resolution topic.
- Improved how the Slack data import tool handles Slack threads.
- Improved the Slack incoming integration's handling of fancier Slack
  syntax.
- Improved notification format for most Git integrations.
- Improved onboarding emails with better content and links to guides.
- Improved how uploaded files are served with the S3 file uploads
  backend to better support browser caching.
- Improved the instructions for data imports from third-party tools to
  be much more detailed.
- Improved the web application's main loading indicator.
- Improved the visuals of todo and poll widgets.
- Improved the content of onboarding emails.
- Improved default for whether to include the Zulip realm name in
  the subject line of email notifications.
- Improved rendering format for emoji inside headings.
- Improved performance of rendering message views.
- Improved capabilities of compliance exports, including new CSV format.
- Fixed missing localization for dates/times in the message feed.
- Fixed a subtle issue causing files uploaded via the incoming email
  gateway to not be viewable.
- Fixed a subtle compose box issue that could cause a message to be
  sent twice.
- Fixed several subtle bugs involving messages that failed to send.
- Fixed several subtle bugs in message feed loading and rendering.
- Fixed several subtle live-update bugs involving moving messages.
- Fixed several error handling bugs in the message edit UI.
- Fixed an issue where newly created users could get email
  notifications for messages from Welcome Bot.
- Fixed an issue the management command to garbage-collect uploaded
  files that are no longer used in a message was not running in cron.
- Fixed noticeable lag when marking messages as unread in the web app.
- Fixed a bug that could cause duplicate mobile push notifications.
- Fixed several error handling issues with the data export process.
- Fixed several subtle issues affecting certain container runtimes.
- Added support for configurable hooks to be run when upgrading the
  Zulip server.
- Added support for using TLS to secure the RabbitMQ connection.
- The Zulip API now includes a `ignored_parameters_unsupported` field
  to help client developers debug when they are attempting to use a
  parameter that the Zulip server does not support.
- Migrated web application error reporting to use Sentry.
- Significant portions of the original Bootstrap CSS framework have
  been deleted. This is an ongoing project.
- Converted many JavaScript modules to TypeScript.
- Reorganized the codebase, with new web/, help/, and api_docs/
  top-level directories.
- Upgraded many third-party dependencies, including to Django 4.2 LTS.

#### Upgrade notes for 7.0

- When the [S3 storage backend](../production/upload-backends.md) is used for
  storing file uploads, those contents are now fetched by nginx, cached locally
  on the server, and served to clients; this lets clients cache the contents,
  and saves them a redirect. However, it may require administrators adjust the
  size of the server's cache if they have a large deploy; see the
  [documentation](../production/upload-backends.md#s3-local-caching).
- Removed the `application_server.no_serve_uploads` setting in
  `/etc/zulip/zulip.conf`, as all uploads requests go through Zulip now.
- Installations using the previously undocumented [JWT authentication
  feature](../production/authentication-methods.md#jwt) will need
  to make minor adjustments in the format of JWT requests; see the
  documentation for details on the new format.
- High volume log files like `server.log` are now by default retained
  for 14 days, configured via the `access_log_retention_days`
  [deployment
  option](../production/system-configuration.md). This
  replaces a harder to understand size-based algorithm that was not
  easily configurable.
- The URL patterns for
  [linkifiers](https://zulip.com/help/add-a-custom-linkifier) have
  been migrated from a custom format string to RFC 6570 URL
  templates. A database migration will automatically migrate existing
  linkifiers correctly in the vast majority of cases, but some fancier
  linkfiers may require manual adjustment to generate correct URLs
  following this upgrade.
- PostgreSQL 11 is no longer supported; if you are currently using it, you will
  need to [upgrade PostgreSQL](../production/upgrade.md#upgrading-postgresql)
  before upgrading Zulip.
- Installations that deploy Zulip behind a [reverse proxy][reverse-proxy-docs]
  should make sure the proxy is configured to set the `X-Forwarded-Proto` HTTP
  header, and that [`loadbalancer.ips` is accurate][loadbalancer-ips] for the
  reverse proxy's IP; the documentation has updated its example configurations.
- Zulip's Twitter preview integration has been disabled due to Twitter
  desupporting the API that it relied on.

[reverse-proxy-docs]: ../production/reverse-proxies.md
[loadbalancer-ips]: ../production/reverse-proxies.md#configuring-zulip-to-trust-proxies

## Zulip Server 6.x series

### Zulip Server 6.2

_Released 2023-05-19_

- CVE-2023-28623: Fixed a vulnerability that would allow users to sign up for a
  Zulip Server account with an unauthorized email address, despite the server
  being configured to require that email addresses be in LDAP. Specifically, if
  the organization permissions don't require invitations to join, and the only
  configured authentication backends were `ZulipLDAPAuthBackend` and some other
  external authentication backend (any aside from `ZulipLDAPAuthBackend` and
  `EmailAuthBackend`), then an unprivileged remote attacker could have created a
  new account in the organization with an arbitrary email address in their
  control that was not in the organization's LDAP directory.
- CVE-2023-32677: Fixed a vulnerability which allowed users to invite new users
  to streams when inviting them to the server, even if they did not have
  [permission to invite existing users to streams](https://zulip.com/help/configure-who-can-invite-to-streams).
  This did not allow users to invite others to streams that they themselves were
  not a member of, and only affected deployments with the rare configuration of
  a permissive
  [realm invitation policy](https://zulip.com/help/restrict-account-creation#change-who-can-send-invitations)
  and a strict
  [stream invitation policy](https://zulip.com/help/configure-who-can-invite-to-streams).
- Fixed a bug that could cause duplicate push notifications when using the
  mobile push notifications service.
- Fixed several bugs in the Zulip server and PostgreSQL version upgrade
  processes.
- Fixed multiple Recent conversations display bugs for private message
  conversations.
- Fixed the left sidebar stream list exiting “more topics” during background
  re-rendering, and a related rendering bug.
- Fixed a bug where uploaded files sent via the email gateway were not correctly
  associated with the message’s sender.
- Improved error handling for certain puppet failures.
- Silenced a distracting `caniuse browserlist` warning in install/upgrade
  output.
- Simplified UI for inviting new users to make it easy to select the default
  streams.
- Fixed GPG check error handling for PGroonga apt repository.
- Documented how to manage email address changes when using the LDAP backend.
- Documented how to use SMTP without authentication.
- Documented that the Zulip mobile/desktop apps now only support Zulip Server
  4.0 and newer (released 22 months ago), following our 18-month support policy.
- Extracted the documentation on modifying Zulip to a dedicated page.
- Added a new `send_welcome_bot_message` management command, to allow the
  sysadmin to send Welcome Bot messages manually after a data import.
- Added new `RABBITMQ_USE_TLS` and `RABBITMQ_PORT` settings for installations
  wanting to configure the RabbitMQ connection with a remote RabbitMQ host.
- Added a new `timesync` deployment option to allow installations to override
  Zulip’s default of `chrony` for time synchronization.
- Upgraded dependencies for security and bug fixes.

### Zulip Server 6.1

_Released 2023-01-23_

- Fixed a bug that caused the web app to not load on Safari 13 and lower;
  affected users would only see a blank page.
- Recent conversations now displays the “Participants” column for private
  messages too.
- Fixed minor bugs in “Recent conversations” focus and re-rendering.
- Fixed bugs that caused some unicode emoji to be incorrectly unavailable.
- Fixed subtle display bugs rendering the left sidebar.
- Fixed a bug causing the message feed to briefly show a “no matching messages”
  notice while loading.
- Fixed a double escaping display bug when displaying user names in an error
  notice.
- Fixed an unhandled exception when displaying user cards if the current user
  has an invalid timezone configured.
- Fixed a subtle interaction bug with the compose box preview widget.
- Added a workaround for a bug in Chromium affecting older versions of the Zulip
  desktop app that would cause horizontal lines to appear between messages.
- Stopped clipping the tops of tall characters in stream and topic names.
- Use internationalized form of “at” in message timestamps.
- Updated translations.
- Fixed the “custom” value for the
  “[delay before sending message notification emails](https://zulip.com/help/email-notifications#delay-before-sending-emails)”
  setting.
- Fixed an error which prevented users from changing
  [stream-specific notification settings](https://zulip.com/help/stream-notifications#configure-notifications-for-a-single-stream).
- Fixed the redirect from `/apps` to https://zulip.com/apps/.
- Started preserving timezone information in
  [Rocket.Chat imports](https://zulip.com/help/import-from-rocketchat).
- Updated the Intercom integration to return success on `HEAD`
  requests, which it uses to verify its configuration.
- Documented how each
  [rate limit](../production/security-model.md#rate-limiting)
  category is used.
- Documented the `reset_authentication_attempt_count` command for when users
  lock themselves out.
- Documented the
  [full S3 bucket policy](../production/upload-backends.md#s3-bucket-policy)
  for avatar and uploads buckets.
- Clarified what the `--email` value passed to the installer will be used for.
- Hid harmless "non-existent database" warnings during initial installation.
- Forced a known locale when upgrading PostgreSQL, which avoids errors when
  using some terminal applications.
- Verified that PostgreSQL was running after upgrading it, in case a previous
  try at an upgrade left it stopped.
- Updated custom emoji migration 0376 to be a single SQL statement, and no
  longer crash when no active owners were found.
- Replaced `transifex-client` internationalization library with new
  `transifex-cli`.
- Began respecting proxy settings when installing `shellcheck` and `shfmt`
  tools.
- Fixed the invitation code to signal a user data validation error, and not a
  server error, if an invalid “invite as” value was given.
- Renamed internal exceptions to end with `Error`.

### Zulip Server 6.0

_Released 2022-11-17_

#### Highlights

- Users can now mark messages as unread.
- Added support for viewing read receipts, along with settings
  allowing both organizations and individual users to disable them.
- Added new compose box button to navigate to the conversation being
  composed to, when that is different from the current view.
- Added a scroll-to-bottom button, analogous to the `End` shortcut,
  that appears only when scrolling using the mouse.
- Added support for up to 2 custom profile fields being highlighted in
  a user's profile summary popover, and added support for a new
  Pronouns custom field type designed to take advantage of
  it. Redesigned the custom profile fields administrative UI.
- Redesigned the left sidebar to better organize pinned and inactive
  streams, highlight topics where the user was mentioned, and better
  advertise streams that the current user can subscribe to.
- Redesigned the private messages experience in the left sidebar to
  make browsing conversations more ergonomic, with a similar usage
  pattern to browsing the topics within a stream.
- Improved "Recent topics" and renamed it to "Recent conversations"
  with the addition of including private messages in the view. The
  timestamp links now go to the latest message in the topic, arrow key
  navigation was improved, topics containing unread mentions are now
  highlighted, as well as many other bug fixes or subtle improvements.
- Messages containing 3 or fewer emoji reactions now display the names
  of reacting users alongside the emoji. This eliminates the need to
  mouse over emoji reactions to find out who reacted in the vast
  majority of cases.
- Replaced the previous "Unavailable" status with a "Go invisible" feature
  that is more useful and intuitive.
- The right sidebar now displays user status messages by default, with
  an optional compact design available.
- The [public access option][public-access-option] was enhanced to
  skip the login page by default, support switching themes and
  languages, and add many other UI improvements.
- Incoming webhook integrations now support filtering which classes of events
  are sent into Zulip; this can be invaluable when the third-party service
  doesn't support configuring which events to send to Zulip.
- Added support for Ubuntu 22.04.
- Removed support for Debian 10 and PostgreSQL 10 due to their
  approaching end-of-life upstream.
- New integrations: Azure DevOps, RhodeCode, wekan.

[public-access-option]: https://blog.zulip.com/2022/05/05/public-access-option/

#### Full feature changelog

- Redesigned the message actions popover to be better organized.
- Redesigned moving messages to have a cleaner, more consistent UI that is no
  longer combined with the message editing UI. One can now choose to send
  automated notices when moving messages within a stream, not only between
  streams.
- Redesigned full user profiles to have a cleaner look and also
  display user IDs, which can be important when using the API. Users
  can now administer bot stream subscriptions from the bot's full
  profile.
- Redesigned the gear menu to display basic details about the Zulip
  organization, server, and its version.
- Redesigned several organization settings pages to have more
  consistent design.
- Redesigned the footer for self-hosted Zulip servers. The footer now has just a
  few key links, rather than being almost identical to the footer for the
  zulip.com website.
- Redesigned the 500 error pages for self-hosted Zulip servers to be
  clearer and link to the Zulip server troubleshooting guide.
- Redesigned the interface for configuring message editing and
  deletion permissions to be easier to understand.
- Added support for emoji added in unicode versions since 2017, which
  had previously been unavailable in Zulip. Users using the deprecated
  "Google blobs" emoji set are automatically migrated to the modern
  "Google" emoji set. The "Google blobs" emoji set remains available
  for users who prefer it, with any new emoji that were added to the
  Unicode standard since 2017 displayed in the modern "Google" style.
- Added support for changing the role of bots in the UI; previously,
  this was only possible via the API.
- Added confirmation modals for various destructive actions, such as
  deactivating bots.
- Added new summary statistics on the organization analytics
  page. Fixed several bugs with the display of analytics graphs.
- Added support for administrators sending a final email to a user as
  part of deactivating their Zulip account.
- Added API endpoint to get a single stream by ID.
- Added beta support for user groups to have subgroups, and for some
  permissions settings to be managed using user groups. Over the
  coming releases, we plan to migrate all Zulip permissions settings
  to be based on this more flexible groups-based system. We currently
  expect this migration to be fully backwards-compatible.
- Added a new compliance export management command.
- Zulip's automated emails use the `X-Auto-Response-Suppress` header
  to reduce auto-responder replies.
- Changed various icons to be more intuitive. The bell-based icon for
  muted topics has been replaced by a more standard muted speaker icon.
- Reworked how a new user's language is set to prefer their browser's
  configured language over the organization's configured
  language. This organization-level setting has been renamed to
  "Language for automated messages and invitation emails" to reflect
  what it actually does following this change.
- Organized the Drafts panel to prioritize drafts matching the current
  view.
- Added an automated notification to the "stream events" topic when
  changing a stream's privacy settings.
- Added support for conveniently overriding the default rate-limiting rules.
- Improved the search typeahead to show profile pictures for users.
- Improved typeahead matching algorithm for stream/user/emoji names
  containing multiple spaces and other corner cases.
- Improved the help center, including better display of keyboard
  shortcuts, mobile documentation for common workflows and many polish
  improvements.
- Improved API documentation, including a new page on roles and
  permissions, an audit to correct missing **Changes** entries, and
  new documentation for several previously undocumented endpoints.
- Improved Python static type-checking to make use of Django stubs for
  `mypy`, fixing many minor bugs in the process.
- Improved RealmAuditLog to cover several previously unauditable changes.
- Improved the experience for users who have not logged in for a long
  time, and receive an email or push notification about a private
  message or personal mention. These users are now automatically soft
  reactivated at the time of the notification, for a smoother
  experience when they log in.
- Improved the Tornado server-to-client push system's sharding system
  to support realm regular expressions and experimental support for
  splitting a single realm across multiple push server processes.
- Improved user deactivation modal to provide details about bots and
  invitations that will be disabled.
- Improve matching algorithm for left sidebar stream filtering.
- Improved several integrations, including CircleCI, Grafana, Harbor,
  NewRelic, and the Slack compatible incoming webhook. Git webhooks
  now use a consistent algorithm for choosing shortened commit IDs to
  display.
- Improved mention typeahead and rendering for cases where mention
  syntax appears next to symbols.
- Improved browser window titles used by the app to be clearer.
- Improved the language in message notification emails explaining
  why the notification was sent.
- Improved interface for accessing stream email addresses.
- Reordered the organization settings panels to be more intuitive.
- Increased timeout for processing slow requests from 20s to 60s.
- Removed the "user list in left sidebar in narrow windows" setting.
- Removed limits that prevented replying to Zulip email notifications multiple
  times or, several days after receiving them.
- Fixed numerous bugs and performance issues with the Rocket.Chat data
  import tool. Improved importing emoji from Slack.
- Fixed several bugs where drafts could fail to be saved.
- Fixed a bug where copy-paste would incorrectly copy an entire message.
- Fixed the app's main loading page to not suggest reloading until
  several seconds have passed.
- Fixed multiple bugs that could cause the web app to flood the server
  with requests after the computer wakes up from suspend.
- Fixed a bug where public streams imported from other chat systems
  could incorrectly be configured as public streams without shared
  history, a configuration not otherwise possible in Zulip.
- Fixed several subtle bugs involving editing custom profile field
  configuration.
- Fixed several bugs involving compose box keyboard shortcuts.
- Fixed dozens of settings UI interaction design bugs.
- Fixed subtle caching bugs in the URL preview system.
- Fixed several rare race conditions in the server implementation.
- Fixed many CSS corner cases issues involving content overflowing containers.
- Fixed entering an emoji in the mobile web app using an emoji
  keyboard.
- Fixed Enter being processed incorrectly when inputting a character
  into Zulip phonetically via an IME composing session.
- Fixed several subtle bugs with confirmation links.
- Fixed a subtle performance issue for full-text search for uncommon words.
- Fixed the estimator for the size of public data exports.
- Fixed "mark all as read" requiring a browser reload.
- Major improvements to our documentation for setting up the development
  environment and for joining the project as a new contributor.
- Extracted several JavaScript modules to share code with the mobile
  app.
- Replaced several Python linters with Ruff, an incredibly fast
  Python linter written in Rust.
- Upgraded many third-party dependencies including Django 4.1, and
  substantially modernized the Python codebase.

#### Upgrade notes for 6.0

- Installations using [docker-zulip][docker-zulip] will need to [upgrade
  Postgres][docker-zulip-upgrade-database] before upgrading to Zulip
  6.0, because the previous default of Postgres 10 is no longer
  supported by this release.
- Installations using the AzureAD authentication backend will need to
  update `/etc/zulip/zulip-secrets.conf` after upgrading. The
  `azure_oauth2_secret` secret was renamed to
  `social_auth_azuread_oauth2_secret`, to match our other external
  authentication methods.
- This release contains an expensive migration,
  `0419_backfill_message_realm`, which adds data to a new `realm`
  column in the message table. Expect it to run for 10-15 minutes per
  million messages in the database. The new column is not yet used in
  this release, so this migration can be run in the background for
  installations hoping to avoid extended downtime.
- Custom profile fields with "Pronouns" in their name and the "short
  text" field type were converted to the new "Pronouns" field type.

[docker-zulip-upgrade-database]: https://github.com/zulip/docker-zulip/#upgrading-zulipzulip-postgresql-to-14

## Zulip Server 5.x series

### Zulip Server 5.7

_Released 2022-11-16_

- CVE-2022-41914: Fixed the verification of the SCIM account
  management bearer tokens to use a constant-time comparator. Zulip
  Server 5.0 through 5.6 checked SCIM bearer tokens using a comparator
  that did not run in constant time. For organizations with SCIM
  account management enabled, this bug theoretically allowed an
  attacker to steal the SCIM bearer token, and use it to read and
  update the Zulip organization’s user accounts. In practice, this
  vulnerability may not have been practical or exploitable. Zulip
  Server installations which have not explicitly enabled SCIM are not
  affected.
- Fixed an error with deactivating users with `manage.py sync_ldap_user_data`
  when `LDAP_DEACTIVATE_NON_MATCHING_USERS` was enabled.
- Fixed several subtle bugs that could lead to browsers reloading
  repeatedly when the server was updated.
- Fixed a live-update bug when changing certain notifications
  settings.
- Improved error logs when sending push notifications to the push
  notifications service fails.
- Upgraded Python requirements.

### Zulip Server 5.6

_Released 2022-08-24_

- CVE-2022-36048: Change the Markdown renderer to only rewrite known
  local links as relative links, rather than rewriting all local
  links. This fix also protects against a vulnerability in the Zulip
  mobile app (CVE-2022-35962).
- Added hardening against timing attacks to an internal authentication check.
- Improved documentation for hosting multiple organizations on a server.
- Updated dependencies.
- Updated translations.

### Zulip Server 5.5

_Released 2022-07-21_

- CVE-2022-31168: Fix authorization check for changing bot roles. Due
  to an incorrect authorization check in Zulip Server 5.4 and all prior
  releases, a member of an organization could craft an API call that
  would grant organization administrator privileges to one of their bots.
- Added new options to the `restore-backup` tool to simplify restoring
  backups on a system with a different configuration.
- Updated translations, including major updates to the Mongolian and
  Serbian translations.

### Zulip Server 5.4

_Released 2022-07-11_

- CVE-2022-31134: Exclude private file uploads from [exports of public
  data](https://zulip.com/help/export-your-organization#export-of-public-data). We
  would like to thank Antoine Benoist for bringing this issue to our
  attention.
- Upgraded python requirements.
- Improved documentation for load balancers to mention CIDR address
  ranges.
- Documented an explicit list of supported CPU architectures.
- Switched `html2text` to run as a subprocess, rather than a Python
  module, as its GPL license is not compatible with Zulip’s.
- Replaced `markdown-include` python module with a reimplementation,
  as its GPL license is not compatible with Zulip’s.
- Relicensed as GPL the `tools/check-thirdparty` developer tool which
  verifies third-party licenses, due to a GPL dependency by way of
  `python-debian`.
- Closed a potential race condition in the Tornado server, with events
  arriving at exactly the same time as request causing server errors.
- Added a tool to help automate more of the release process.

### Zulip Server 5.3

_Released 2022-06-21_

- CVE-2022-31017: Fixed message edit event exposure in
  protected-history streams.
  Zulip allows a stream to be configured as [private with protected
  history](https://zulip.com/help/stream-permissions#stream-privacy-settings),
  which means that new subscribers should only see messages sent after
  they join. However, due to a logic bug in Zulip Server 2.1.0 through
  5.2, when a message was edited, the server would incorrectly send an
  API event that included both the edited and old content of the
  message to all of the stream’s current subscribers, regardless of
  whether they could see the original message. The impact of this
  issue was reduced by the fact that this API event is ignored by
  official clients, so it could only be observed by a user using a
  modified client or their browser’s developer tools.
- Adjusted upgrade steps to cause servers using PostgreSQL 14 to
  upgrade to PostgreSQL 14.4, which fixes an important potential
  database corruption issue.
- Upgraded the asynchronous request handling to use Tornado 6.
- Fixed a crash when displaying the error message for a failed attempt
  to create a stream.
- Optimized the steps during `upgrade-zulip`, to reduce the amount of
  server downtime.
- Added a `--skip-restart` flag to `upgrade-zulip` which prepares the
  new version, but does not restart the server into it.
- Stopped mirroring the entire remote Git repository directly into
  `/srv/zulip.git`. This mirroring removed local branches and confused
  the state of previous deployments.
- Fixed a bug which could cause the `delete_old_unclaimed_attachments`
  command-line tool to remove attachments that were still referenced
  by deleted (but not yet permanently removed) messages.
- Stopped enabling `USE_X_FORWARDED_HOST` by default, which was
  generally unneeded; the proxy documentation now clarifies when it is
  necessary.
- Fixed the nginx configuration to include the default system-level
  nginx modules.
- Only attempt to fix the `certbot` SSL renewal configuration if HTTPS
  is enabled; this addresses a regression in Zulip Server 5.2, where
  the upgrade would fail if an improperly configured certificate
  existed, but was both expired and not in use.
- Improved proxy and database backup documentation.

### Zulip Server 5.2

_Released 2022-05-03_

- Fixed a performance regression in the UI, introduced in 5.0, when
  opening the compose box.
- Fixed a bug which could intermittently cause URL previews to fail,
  if Zulip was being run in Docker or in low-memory environments.
- Fixed an issue which would cause PostgreSQL 10 and PostgreSQL 11 to
  attempt to write each WAL log to S3, even if S3 WAL
  backups/replication were not configured.
- Fixed an issue which prevented the SCIM integration from
  deactivating users.
- Fixed a bug that resulted in an “You unsubscribed” notice
  incorrectly appearing when new messages arrived in a topic being
  viewed via a “near” link.
- Fixed digest emails being incorrectly sent if a user was deactivated
  after the digest was enqueued but before it was processed.
- Fixed warning about `EMAIL_HOST_PASSWORD` being unset when
  explicitly set to empty.
- Fixed incomplete tracebacks when timeouts happen during Markdown
  rendering.
- Fixed some older versions of Zulip Server not being considered when
  comparing for the likely original version of `settings.py`.
- Stopped using the `database_password` if it is set but
  `database_user` is not.
- Stopped trying to fix LetsEncrypt certificate configuration if they
  were not currently in use.
- Sorted and prettified the output of the
  `check-database-compatibility` tool.
- Split the large `zerver/lib/actions.py` file into many files under
  `zerver/actions/`. This non-functional change was backported to
  ensure it remains easy to backport other changes.
- Updated documentation to reflect that current mobile apps are only
  guaranteed to be compatible with Zulip Server 3.0 and later; they
  may also work with earlier versions, with a degraded experience.

### Zulip Server 5.1

_Released 2022-04-01_

- Fixed upgrade bug where preexisting animated emoji would still
  always animate in statuses.
- Improved check that prevents servers from accidentally downgrading,
  to not block upgrading servers that originally installed Zulip
  Server prior to mid-2017.
- Fixed email address de-duplication in Slack imports.
- Prevented an extraneous scrollbar when a notification banner was
  present across the top.
- Fixed installation in LXC containers, which failed due to `chrony`
  not being runnable there.
- Prevented a "push notifications not configured" warning from
  appearing in the new user default settings panel even when push
  notifications were configured.
- Fixed a bug which, in uncommon configurations, would prevent Tornado
  from being restarted during upgrades; users would be able to log in,
  but would immediately be logged out.
- Updated translations.

### Zulip Server 5.0

_Released 2022-03-29_

#### Highlights

- New [resolve topic](https://zulip.com/help/resolve-a-topic) feature
  allows marking topics as ✔ completed. It’s a lightweight way to
  manage a variety of workflows, including support interactions,
  answering questions, and investigating issues.
- Administrators may enable the option to create [web-public
  streams](https://zulip.com/help/public-access-option). Web-public
  streams can be viewed by anyone on the Internet without creating an
  account in your organization.
- Users can now select a status emoji alongside their status
  message. Status emoji are shown next to the user's name in the
  sidebars, message feed, and compose box. Animated status emoji will
  only animate on hover.
- Redesigned the compose box, adding formatting buttons for bold,
  italics and links as well as visual improvements. New button for
  inserting global times into your message.
- Redesigned "Stream settings" to be much more usable, with separate
  tabs for personal settings, global settings, and membership, and
  more consistent style with the rest of Zulip's settings.
- Stream creation was redesigned with a much cleaner interface,
  especially for selecting initial subscribers.
- Redesigned "Full user profile" widget to show the user's stream and
  user group subscriptions. Administrators can unsubscribe a user from
  streams directly from their full profile.
- Reorganized personal and organization settings to have clearer
  labels and make it easier to find privacy settings.
- Organization administrators can now configure the default personal
  preference settings for new users joining the organization.
- Most permissions settings now support choosing which roles have the
  permission, rather than just allowing administrators or everyone.
- Permanent links to conversations now correctly redirect if the
  target message has been moved to a new stream or topic.
- Added a data import tool for migrating from Rocket.Chat. Mattermost
  data import now supports importing uploaded files.
- Improved handling of messages containing many images; now up to 20
  images can be previewed in a single message (up from 5), and a new
  grid layout will be used.
- OpenID Connect joins SAML, LDAP, Google, GitHub, Azure Active
  Directory, and more as a supported Single Sign-On provider.
- SAML authentication now supports syncing custom profile
  fields. Additionally, SAML authentication now supports automatic
  account creation and IdP-initiated logout.
- Added SCIM integration for synchronizing accounts with an external
  user database.
- Added support for installation on ARM platforms (including Mac M1).
- Removed support for Ubuntu 18.04, which no longer receives upstream
  security support for key Zulip dependencies.

#### Upgrade notes for 5.0

- This release contains a migration, `0009_confirmation_expiry_date_backfill`,
  that can take several minutes to run on a server with millions of
  messages of history.
- The `TERMS_OF_SERVICE` and `PRIVACY_POLICY` settings have been
  removed in favor of a system that supports additional policy
  documents, such as a code of conduct. See the [updated
  documentation](../production/settings.md) for the new system.

#### Full feature changelog

- Timestamps in Zulip messages are now permanent links to the message
  in its thread.
- Added support for invitation links with configurable expiry,
  including links that never expire. Deactivating a user now disables
  all invitations that the user had sent.
- Added support for expanding the compose box to be full-screen.
- Added support for filtering events in webhooks.
- Added support for overriding Zulip's defaults for new users in your
  organization.
- Added support for referring to a user group with a silent mention.
- Added new personal privacy setting controlling whether typing
  notifications are sent to other users.
- Added new personal setting controlling whether `Esc` navigates the
  user to the default view.
- Split stream creation policy into separate settings for private,
  public, and web-public streams.
- New integrations: Freshstatus, Lidarr, Open Collective, Radarr,
  Sonarr, SonarQube.
- Message edit notifications now indicate how many messages were
  moved, when only part of a topic was moved.
- Muted topic records are now moved when an entire topic is moved.
- Search views that don't mark messages as read now have an
  explanatory notice if any unread messages are present.
- Added new "Scroll to bottom" widget hovering over the message feed.
- Changed the default emoji set from Google Classic to Google Modern.
- User groups mentions now correctly function as silent mentions when
  inside block quotes.
- Messages that have been moved (but not otherwise edited) are now
  displayed as MOVED, not EDITED.
- Reworked the UI for selecting a stream when moving topics.
- Redesigned modals in the app to have more consistent and cleaner UX.
- Added new topic filter widget in left sidebar zoomed view.
- Redesigned Welcome Bot onboarding experience.
- Redesigned hover behavior for timestamps and time mentions.
- Messages sent by muted users can now be rehidden after being
  revealed. One can also now mute deactivated users.
- Rewrote Help Center guides for new organizations and users, and made
  hundreds of other improvements to Help Center content and organization.
- Reimplemented the image lightbox's pan/zoom functionality to be
  nicer, allowing us to enable it be default.
- Added styled loading page for the web application.
- Webhook integrations now support specifying the target stream by ID.
- Notifications now differentiate user group mentions from personal mentions.
- Added support for configuring how long the server should wait before
  sending email notifications after a mention or PM.
- Improved integrations: BigBlueButton, GitHub, Grafana, PagerDuty,
  and many more.
- Improved various interaction and performance details in "Recent topics".
- Improved styling for poll and todo list widgets.
- Zulip now supports configuring the database name and username when
  using a remote Postgres server. Previously, these were hardcoded to "zulip".
- Migrated many tooltips to prettier tooltips powered by TippyJS.
- Autocomplete is now available when editing topics.
- Typeahead for choosing a topic now consistently fetches the full set
  of historical topics in the stream.
- Changed "Quote and reply" to insert quoted content at the cursor when
  the compose box is not empty.
- The compose box now has friendly UI for messages longer than 10K characters.
- Compose typeahead now opens after typing only "@".
- Improved the typeahead sorting for choosing code block languages.
- Many additional subtle usability improvements to compose typeahead.
- Adjusted permissions to only allow administrators to override
  unicode emoji with a custom emoji of the same name.
- New "Manage this user" option in user profile popovers simplifies moderation.
- New automated notifications when changing global stream settings
  like description and message retention policy.
- Drafts are now advertised more prominently, in the left sidebar.
- Drafts and message edit history now correctly render widgets like
  spoilers and global times.
- Improved the tooltip formatting for global times.
- LDAP userAccountControl logic now supports FreeIPA quirks.
- Fixed a problem where self-hosted servers that permuted the IDs of
  their users by using the data export/import tools might send mobile
  push notifications to the wrong devices.
- Fixed various bugs resulting in missing translations; most
  importantly in the in-application search/markdown/hotkeys help widgets.
- Fixed several bugs that prevented browser undo from working in the
  compose box.
- Fixed search typeahead not working once you've added a full-text keyword.
- Fixed linkifier validation to prevent invalid linkifiers.
- Fixed `Ctrl+.` shortcut not working correctly with empty topics.
- Fixed numerous corner case bugs with email and mobile push notifications.
- Fixed a bug resulting in long LaTeX messages failing to render.
- Fixed buggy logic displaying users' last active time.
- Fixed confusing "delete stream" language for archiving streams.
- Fixed exceptions in races involving messages being deleted while
  processing a request to add emoji reactions, mark messages as read,
  or sending notifications.
- Fixed most remaining 500 errors seen in Zulip Cloud (these were
  already quite rare, so this process involved debugging several rare
  races, timeouts, and error handling bugs.).
- Fixed subtle bugs involving composing messages to deactivated users.
- Fixed subtle bugs with reloading the page while viewing settings
  with "Recent topics" as the default view.
- Fixed bug where pending email notifications could be lost when restarting
  the Zulip server.
- Fixed "require topics" setting not being enforced for API clients.
- Fixed several subtle Markdown rendering bugs.
- Fixed several bugs with message edit history and stream/topic moves.
- Fixed multiple subtle bugs that could cause compose box content to
  not be properly saved as drafts in various situations.
- Fixed several server bugs involving rare race conditions.
- Fixed a bug where different messages in search results would be
  incorrectly shown with a shared recipient bar despite potentially
  not being temporally adjacent.
- Fixed lightbox download button not working with the S3 upload backend.
- Increased default retention period before permanently removing
  deleted messages from 7 days to 30 days.
- Rate limiting now supports treating all Tor exit nodes as a single IP.
- Changed "From" header in invitation emails to no longer include the
  name of the user who sent the invitation, to prevent anti-phishing
  software from flagging invitations.
- Added support for uploading animated PNGs as custom emoji.
- Renamed "Night mode" to "Dark theme".
- Added the mobile app's notification sound to desktop sound options,
  as "Chime".
- Reworked the `manage.py help` interface to hide Django commands that are
  useless or harmful to run on a production system. Also deleted
  several useless management commands.
- Improved help and functionality of several management commands. New
  create_realm management command supports some automation workflows.
- Added `RealmAuditLog` logging for most administrative actions that
  were previously not tracked.
- Added automated testing of the upgrade process from previous releases,
  to reduce the likelihood of problems upgrading Zulip.
- Attempting to "upgrade" to an older version now gives a clear error
  message.
- Optimized critical parts of the message sending code path for large
  organizations.
- Optimized creating streams in very large organizations.
- Certain unprintable Unicode characters are no longer permitted in
  topic names.
- Added IP-based rate limiting for unauthenticated requests.
- Added documentation for Zulip's rate-limiting rules.
- Merged the API endpoints for a user's personal settings into the
  /settings endpoint with a cleaner interface.
- The server API now supports marking messages as unread, allowing
  this upcoming mobile app feature to work with Zulip 5.0.
- Added to the API most page-load parameters used by the web app
  application that were missing from the `/register` API.
- Simplified the infrastructure for rendering API documentation so
  that only a few pages require Markdown templates in addition to the
  OpenAPI specification file.
- Corrected many minor issues with the API documentation.
- Major improvements to both the infrastructure and content for
  Zulip's ReadTheDocs documentation for contributors and sysadmins.
- Major improvements to the mypy type-checking, discovered via
  using the django-stubs project to get Django stubs.
- Renamed main branch from `master` to `main`.

## Zulip Server 4.x series

### Zulip Server 4.11

_Released 2022-03-15_

- CVE-2022-24751: Zulip Server 4.0 and above were susceptible to a
  race condition during user deactivation, where a simultaneous access
  by the user being deactivated may, in rare cases, allow continued
  access by the deactivated user. This access could theoretically
  continue until one of the following events happens:
  - The session expires from memcached; this defaults to two weeks, and
    is controlled by SESSION_COOKIE_AGE in /etc/zulip/settings.py
  - The session cache is evicted from memcached by other cached data.
  - The server is upgraded, which clears the cache.
- Updated translations.

### Zulip Server 4.10

_Released 2022-02-25_

- CVE-2022-21706: Reusable invitation links could be improperly used
  for other organizations.
- CVE-2021-3967: Enforce that regenerating an API key must be done
  with an API key, not a cookie. Thanks to nhiephon
  (twitter.com/\_nhiephon) for their responsible disclosure of this
  vulnerability.
- Fixed a bug with the `reindex-textual-data` tool, where it would
  sometimes fail to find the libraries it needed.
- Pin PostgreSQL to 10.19, 11.14, 12.9, 13.5 or 14.1 to avoid a
  regression which caused deploys with PGroonga enabled to
  unpredictably fail database queries with the error
  `variable not found in subplan target list`.
- Fix ARM64 support; however, the wal-g binary is not yet supported on
  ARM64 (zulip/zulip#21070).

### Zulip Server 4.9

_Released 2022-01-24_

- CVE-2021-43799: Remote execution of code involving RabbitMQ.
- Closed access to RabbitMQ port 25672; initial installs tried to
  close this port, but failed to restart RabbitMQ for the
  configuration.
- Removed the `rabbitmq.nodename` configuration in `zulip.conf`; all
  RabbitMQ instances will be reconfigured to have a nodename of
  `zulip@localhost`. You can remove this setting from your
  `zulip.conf` configuration file, if it exists.
- Added missing support for the Camo image proxy in the Docker
  image. This resolves a longstanding issue with image previews, if
  enabled, appearing as broken images for Docker-based installs.
- Fixed a bug which allowed a user to edit a message to add a wildcard
  mention when they did not have permissions to send such messages
  originally.
- Fixed a bug in the tool that corrects database corruption caused by
  updating the operating system hosting PostgreSQL, which previously
  omitted some indexes from its verification. If you updated the
  operating system of your Zulip instance from Ubuntu 18.04 to 20.04,
  or from Debian 9 to 10, you should run the tool,
  even if you did so previously; full details and instructions are
  available in the previous blog post.
- Began routing requests from the Camo image proxy through a
  non-Smokescreen proxy, if one is configured; because Camo includes
  logic to deny access to private subnets, routing its requests
  through Smokescreen is generally not necessary.
- Fixed a bug where changing the Camo secret required running
  `zulip-puppet-apply`.
- Fixed `scripts/setup/compare-settings-to-template` to be able to run
  from any directory.
- Switched Let's Encrypt renewal to use its own timer, rather than our
  custom cron job. This fixes a bug where occasionally `nginx` would
  not reload after getting an updated certificate.
- Updated documentation and tooling to note that installs using
  `upgrade-zulip-from-git` require 3 GB of RAM, or 2 GB and at least 1
  GB of swap.

### Zulip Server 4.8

_Released 2021-12-01_

- CVE-2021-43791: Zulip could fail to enforce expiration dates
  on confirmation keys, allowing users to potentially use expired
  invitations, self-registrations, or realm creation links.
- Began installing Smokescreen to harden Zulip against SSRF attacks by
  default. Zulip has offered Smokescreen as an option since Zulip
  4.0. Existing installs which configured an outgoing proxy which is
  not on `localhost:4750` will continue to use that; all other
  installations will begin having a Smokescreen installation listening
  on 127.0.0.1, which Zulip will proxy traffic through. The version of
  Smokescreen was also upgraded.
- Replaced the camo image proxy with go-camo, a maintained
  reimplementation that also protects against SSRF attacks. This
  server now listens only on 127.0.0.1 when it is deployed as part of
  a standalone deployment.
- Began using camo for images displayed in URL previews. This improves
  privacy and also resolves an issue where an image link to a third
  party server with an expired or otherwise invalid SSL certificate
  would trigger a confusing pop-up window for Zulip Desktop users.
- Fixed a bug which could cause Tornado to shut down improperly
  (causing an immediate full-page reload for their clients) when
  restarting a heavily loaded Zulip server.
- Updated Python dependencies.
- Truncated large “remove” mobile notification events so that marking
  hundreds of private messages or other notifiable messages as read at
  once won’t exceed Apple’s 4 KB notification size limit.
- Slack importer improvements:
  - Ensured that generated fake email addresses for Slack bots are
    unique.
  - Added support for importing Slack exports from a directory, not
    just a .zip file.
  - Provided better error messages with invalid Slack tokens.
  - Added support for non-ASCII Unicode folder names on Windows.
- Add support for V3 Pagerduty webhook.
- Updated documentation for Apache SSO, which now requires additional
  configuration now that Zulip uses a C extension (the `re2` module).
- Fixed a bug where an empty name in a SAML response would raise an
  error.
- Ensured that `deliver_scheduled_emails` and
  `deliver_scheduled_messages` did not double-deliver if run on
  multiple servers at once.
- Extended Certbot troubleshooting documentation.
- Fixed a bug in soft deactivation catch-up code, in cases where a
  race condition had created multiple subscription deactivation
  entries for a single user and single stream in the audit log.
- Updated translations, including adding a Sinhala translation.

### Zulip Server 4.7

_Released 2021-10-04_

- CVE-2021-41115: Prevent organization administrators from affecting
  the server with a regular expression denial-of-service attack
  through linkifier patterns.

### Zulip Server 4.6

_Released 2021-09-23_

- Documented official support for Debian 11 Bullseye, now that it is
  officially released by Debian upstream.
- Fixed installation on Debian 10 Buster. Upstream infrastructure had
  broken the Python `virtualenv` tool on this platform, which we've
  worked around for this release.
- Zulip releases are now distributed from https://download.zulip.com/server/,
  replacing the old `www.zulip.org` server.
- Added support for LDAP synchronization of the `is_realm_owner` and
  `is_moderator` flags.
- `upgrade-zulip-from-git` now uses `git fetch --prune`; this ensures
  `upgrade-zulip-from-git master` with return an error rather than
  using a stale cached version of the `master` branch, which was
  renamed to `main` this month.
- Added a new `reset_authentication_attempt_count` management command
  to allow sysadmins to manually reset authentication rate limits.
- Fixed a bug that caused the `upgrade-postgresql` tool to
  incorrectly remove `supervisord` configuration for `process-fts-updates`.
- Fixed a rare migration bug when upgrading from Zulip versions 2.1 and older.
- Fixed a subtle bug where the left sidebar would show both old and
  new names for some topics that had been renamed.
- Fixed incoming email gateway support for configurations
  with the `http_only` setting enabled.
- Fixed issues where Zulip's outgoing webhook, with the
  Slack-compatible interface, had a different format from Slack's
  documented interface.
- The installation and upgrade documentations now show the latest
  release's version number.
- Backported many improvements to the ReadTheDocs documentation.
- Updated translation data from Transifex.

### Zulip Server 4.5

_Released 2021-07-25_

- Added a tool to fix potential database corruption caused by host OS
  upgrades (was listed in 4.4 release notes, but accidentally omitted).

### Zulip Server 4.4

_Released 2021-07-22_

- Fixed a possible denial-of-service attack in Markdown fenced code
  block parsing.
- Smokescreen, if installed, now defaults to only listening on
  127.0.0.1; this prevents it from being used as an open HTTP proxy if
  it did not have other firewalls protecting incoming port 4750.
- Fixed a performance/scalability issue for installations using the S3
  file uploads backend.
- Fixed a bug where users could turn other users’ messages they could
  read into widgets (e.g. polls).
- Fixed a bug where emoji and avatar image requests were sent through
  Camo; doing so does not add any security benefit, and broke custom
  emoji that had been imported from Slack in Zulip 1.8.1 or earlier.
- Changed to log just a warning, instead of an exception, in the case
  that the `embed_links` worker cannot fetch previews for all links in
  a message within the 30-second timeout. Each preview request within
  a message already has a 15-second timeout.
- Ensured `psycopg2` is installed before starting
  `process_fts_updates`; otherwise, it might fail to start several
  times before the package was installed.
- Worked around a bug in supervisor where, when using SysV init,
  `/etc/init.d/supervisor restart` would only have stopped, not
  restarted, the process.
- Modified upgrade scripts to better handle failure, and suggest next
  steps and point to logs.
- Zulip now hides the “show password” eye icon that IE and Edge
  browsers place in password inputs; this duplicated the
  already-present JavaScript-based functionality.
- Fixed “OR” glitch on login page if SAML authentication is enabled
  but not configured.
- The `send_test_email` management command now shows the full SMTP
  conversation on failure.
- Provided a `change_password` management command which takes a
  `--realm` option.
- Fixed `upgrade-zulip-from-git` crashing in CSS source map generation
  on 1-CPU systems.
- Added an `auto_signup` field in SAML configuration to auto-create
  accounts upon first login attempt by users which are authenticated
  by SAML.
- Provided better error messages when `puppet_classes` in `zulip.conf`
  are mistakenly space-separated instead of comma-separated.
- Updated translations for many languages.

### Zulip Server 4.3

_Released 2021-06-02_

- Fixed exception when upgrading older servers with the
  `JITSI_SERVER_URL` setting set to `None` to disable Jitsi.
- Fixed GIPHY integration dropdown appearing when the server
  doesn't have a GIPHY API key configured.
- The GIPHY API library is no longer loaded for users who are not
  actively using the GIPHY integration.
- Improved formatting for Grafana integration.
- Fixed previews of Dropbox image links.
- Fixed support for storing avatars/emoji in non-S3 upload backends.
- Fixed an overly strict database constraint for code playgrounds.
- Tagged user status strings for translation.
- Updated translation data from Transifex.

### Zulip Server 4.2

_Released 2021-05-13_

- Fixed exception in purge-old-deployments when upgrading on
  a system that has never upgraded using Git.
- Fixed installation from a directory readable only by root.

### Zulip Server 4.1

_Released 2021-05-13_

- Fixed exception upgrading to the 4.x series from older releases.

### Zulip Server 4.0

_Released 2021-05-13_

#### Highlights

- Code blocks now have a copy-to-clipboard button and can be
  integrated with external code playgrounds, making it convenient to
  work with code while discussing it in Zulip.
- Added a new organization [Moderator role][roles-and-permissions].
  Many permissions settings for sensitive features now support only
  allowing moderators and above to use the feature.
- Added a native Giphy integration for sending animated GIFs.
- Added support for muting another user.
- "Recent topics" is no longer beta, no longer an overlay, supports
  composing messages, and is now the default view. The previous
  default view, "All messages", is still available, and the default
  view can now be configured via "Display settings".
- Completed API documentation for Zulip's real-time events system. It
  is now possible to write a decent Zulip client with minimal
  interaction with the Zulip server development team.
- Added new organization settings: wildcard mention policy.
- Integrated [Smokescreen][smokescreen], an outgoing proxy designed to
  help protect against SSRF attacks; outgoing HTTP requests that can
  be triggered by end users are routed through this service.
  We recommend that self-hosted installations configure it.
- This release contains more than 30 independent changes to the [Zulip
  API](https://zulip.com/api/changelog), largely to support new
  features or make the API (and thus its documentation) clearer and
  easier for clients to implement. Other new API features support
  better error handling for the mobile and terminal apps.
- The frontend internationalization library was switched from i18next
  to FormatJS.
- The button for replying was redesigned to show the reply recipient
  and be more obvious to users coming from other chat apps.
- Added support for moving topics to private streams, and for configuring
  which roles can move topics between streams.

[roles-and-permissions]: https://zulip.com/help/roles-and-permissions

#### Upgrade notes for 4.0

- Changed the Tornado service to use 127.0.0.1:9800 instead of
  127.0.0.1:9993 as its default network address, to simplify support
  for multiple Tornado processes. Since Tornado only listens on
  localhost, this change should have no visible effect unless another
  service is using port 9800.
- Zulip's top-level puppet classes have been renamed, largely from
  `zulip::foo` to `zulip::profile::foo`. Configuration referencing
  these `/etc/zulip/zulip.conf` will be automatically updated during
  the upgrade process, but if you have a complex deployment or you
  maintain `zulip.conf` is another system (E.g. with the [manual
  configuration][docker-zulip-manual] option for
  [docker-zulip][docker-zulip]), you'll want to manually update the
  `puppet_classes` variable.
- Zulip's supervisord configuration now lives in `/etc/supervisor/conf.d/zulip/`
- Consider enabling [Smokescreen][smokescreen]
- Private streams can no longer be default streams (i.e. the ones new
  users are automatically added to).
- New `scripts/start-server` and `scripts/stop-server` mean that
  one no longer needs to use `supervisorctl` directly for these tasks.
- As this is a major release, we recommend [carefully updating the
  inline documentation in your
  `/etc/zulip/settings.py`][update-settings-docs]. Notably, we rewrote the
  template to be better organized and more readable in this release.
- The web app will now display a warning in the UI if the Zulip server
  has not been upgraded in more than 18 months.
  template to be better organized and more readable.
- The next time users log in to Zulip with their password after
  upgrading to this release, they will be logged out of all active
  browser sessions (i.e. the web and desktop apps). This is a side
  effect of improved security settings (increasing the minimum entropy
  used when salting passwords from 71 bits to 128 bits).
- We've removed the partial Thumbor integration from Zulip. The
  Thumbor project appears to be dead upstream, and we no longer feel
  comfortable including it in Zulip from a security perspective. We
  hope to introduce a fully supported thumbnailing integration in our next
  major release.

[docker-zulip-manual]: https://github.com/zulip/docker-zulip#manual-configuration
[smokescreen]: ../production/deployment.md#customizing-the-outgoing-http-proxy
[update-settings-docs]: ../production/upgrade.md#updating-settingspy-inline-documentation

#### Full feature changelog

- Added new [release lifecycle documentation](release-lifecycle.md).
- Added support for subscribing another stream's membership to a stream.
- Added RealmAuditLog for most settings state changes in Zulip; this
  data will facilitate future features showing a log of activity by
  a given user or changes to an organization's settings.
- Added support for using Sentry for processing backend exceptions.
- Added documentation for using `wal-g` for continuous PostgreSQL backups.
- Added loading spinners for message editing widgets.
- Added live update of compose placeholder text when recipients change.
- Added keyboard navigation for popover menus that were missing it.
- Added documentation for all [zulip.conf settings][zulip-conf-settings].
- Added dozens of new notification sound options.
- Added menu option to unstar all messages in a topic.
- Added confirmation dialog before unsubscribing from a private stream.
- Added confirmation dialog before deleting your profile picture.
- Added types for all parameters in the API documentation.
- Added API endpoint to fetch user details by email address.
- Added API endpoint to fetch presence details by user ID.
- Added new LDAP configuration options for servers hosting multiple organizations.
- Added new `@**|user_id**` mention syntax intended for use in bots.
- Added preliminary support for Zulip on Debian 11; this
  release is expected to support Debian 11 without any further changes.
- Added several useful new management commands, including
  `change_realm_subdomain` and `delete_user`.
- Added support for subscribing all members of a user group to a stream.
- Added support for sms: and tel: links.
- Community topic editing time limit increased to 3 days for members.
- New integrations: Freshping, Jotform, UptimeRobot, and a JSON
  formatter (which is particularly useful when developing a new
  integration).
- Updated integrations: Clubhouse, NewRelic, Bitbucket, Zabbix.
- Improved formatting of GitHub and GitLab integrations.
- Improved the user experience for multi-user invitations.
- Improved several rendered-message styling details.
- Improved design of `<time>` widgets.
- Improved format of `nginx` logs to include hostname and request time.
- Redesigned the left sidebar menu icons (now `\vdots`, not a chevron).
- The Zoom integration is now stable (no longer beta).
- Favicon unread counts are more attractive and support large numbers.
- Zulip now displays the total number of starred messages in the left
  sidebar by default; over 20% of users had enabled this setting manually.
- Presence circles for users are now shown in mention typeahead.
- Email notifications for new messages are now referred to as a
  "Message notification email", not a "Missed message email".
- Zulip now sets List-Unsubscribe headers in outgoing emails with
  unsubscribe links.
- Password forms now have a "Show password" widget.
- Fixed performance issues when creating hundreds of new users in
  quick succession (E.g. at the start of a conference or event).
- Fixed performance issues in organizations with thousands of online users.
- Fixed numerous rare exceptions when running Zulip at scale.
- Fixed several subtle installer bugs.
- Fixed various UI and accessibility issues in the registration and new
  user invitation flows.
- Fixed live update and UI bugs with streams being deactivated or renamed.
- Fixed a subtle Firefox bug with `Esc` breaking keyboard accessibility.
- Fixed name not being populated currently with Apple authentication.
- Fixed several subtle bugs in the "Stream settings" UI.
- Fixed error handling for incoming emails that fail to send.
- Fixed a subtle bug with timestamps for messages that take a long
  time to send.
- Fixed missing horizontal scrollbar for overflowing rendered LaTeX.
- Fixed visual issues with bottoms areas of both sidebars.
- Fixed several error handling bugs with outgoing webhooks.
- Fixed bugs with recipient bar UI for muting and topic editing.
- Fixed highlighting of adjacent alert words.
- Fixed many settings API endpoints with unusual string encoding.
- Fixed wildcard mentions in blockquotes not being treated as silent.
- Increased size of typeahead box for mentions from 5 to 8.
- Typeahead now always ranks exact string matches first.
- Tooltips have been migrated from Bootstrap to TippyJS, and added
  in many places that previously just had `title` attributes.
- Zulip now consistently uses the Source Code Pro font for code
  blocks, rather than varying by operating system.
- Redesigned "Alert words" settings UI.
- Linkifiers can now be edited in their settings page.
- Tables in settings UI now have sticky headers.
- Confirmation dialogs now consistently use Confirm/Cancel as button labels.
- Refactored typeahead and emoji components to be shareable with the
  mobile codebase.
- Switched to `orjson` for JSON serialization, resulting in better
  performance and more standards-compliant validation.
- Outgoing webhooks now enforce a 10 second timeout.
- Image previews in a Zulip message are now unconditionally proxied by
  Camo to improve privacy, rather than only when the URL was not HTTPS.
- Replaced the old CasperJS frontend test suite with Puppeteer.
- Split the previous `api_super_user` permission into
  `can_create_user` and `can_forge_sender` (used for mirroring).
- Various API endpoints creating objects now return the ID of the
  created object.
- Fixed screen reader accessibility of many components, including
  the compose box, message editing, popovers, and many more.
- Fixed transparency issues uploading some animated GIFs as custom emoji.
- Improved positioning logic for inline YouTube previews.
- Improved performance of several high-throughput queue processors.
- Improved performance of queries that fetch all active subscribers to
  a stream or set of streams.
- Improved performance of sending messages to streams with thousands
  of subscribers.
- Upgraded our ancient forked version of bootstrap, on a path towards
  removing the last forked dependencies from the codebase.
- Upgraded Django to 3.1 (as well as essentially every other dependency).
- Updated web app codebase to use many modern ES6 patterns.
- Upgraded Zulip's core font to Source Sans 3, which supports more languages.
- Relabeled :smile: and :stuck_out_tongue: emoji to use better codepoints.
- Reduced the size of Zulip's main JavaScript bundle by removing `moment.js`.
- Server logs now display the version number for Zulip clients.
- Simplified logic for responsive UI with different browser sizes.
- Fixed several subtle bugs in the compose and message-edit UIs.
- Reduced the steady-state load for an idle Zulip server.
- Removed HipChat import tool, because HipChat has been long EOL.
- Reformatted the Python codebase with Black, and the frontend
  codebase with Prettier.
- Migrated testing from CircleCI to GitHub Actions.

[zulip-conf-settings]: ../production/system-configuration.md

## Zulip Server 3.x series

### Zulip Server 3.4

_Released 2021-04-14_

- CVE-2021-30487: Prevent administrators from moving topics to
  disallowed streams.
- CVE-2021-30479: Prevent guest user access to `all_public_streams`
  API.
- CVE-2021-30478: Prevent API super users from forging messages to
  other organizations.
- CVE-2021-30477: Prevent outgoing webhook bots from sending arbitrary
  messages to any stream.
- Fixed a potential HTML injection bug in outgoing emails.
- Fixed Postfix configuration error which would prevent outgoing email
  to any email address containing `.`, `+`, or starting with `mm`, when
  configured to use the local Postfix to deliver outgoing email.
- Fixed a backporting error which caused the
  `manage.py change_user_role` tool to not work for `admin`, `member`,
  or `guest` roles.
- Add support for logout events sent from modern versions of the
  desktop application.
- Upgraded minor python dependencies.
- Minor documentation fixes.

### Zulip Server 3.3

_Released 2020-12-01_

- Guest users should not be allowed to post to streams marked “Only
  organization full members can post.” This flaw has existed since
  the feature was added in Zulip Server 3.0.
- Permit outgoing mail from postfix; this resolves a bug introduced in
  Zulip Server 3.2 which prevented Zulip from sending outgoing mail if
  the local mail server (used mostly for incoming mail) was also used
  for outgoing email (`MAIL_HOST='localhost'`).
- Ensure that the `upgrade-postgres` tool upgrades the cluster’s data
  to the specific PostgreSQL version requested; this resolves a bug
  where, now that PostgreSQL 13 has been released, `upgrade-postgres`
  would attempt to upgrade to that version and not PostgreSQL 12.
- Replace the impenetrably-named `./manage.py knight` with
  `./manage.py change_user_role`, and extend it to support
  “Organization owner” roles.
- Handle realm emojis that have been manually deleted more gracefully.

### Zulip Server 3.2

_Released 2020-09-15_

- Switched from `libmemcached` to `python-binary-memcached`, a
  pure-Python implementation; this should eliminate memcached
  connection problems affecting some installations.
- Removed unnecessary `django-cookies-samesite` dependency, which had
  its latest release removed from PyPI (breaking installation of Zulip
  3.1).
- Limited which local email addresses Postfix accepts when the
  incoming email integration is enabled; this prevents the enumeration
  of local users via the email system.
- Fixed incorrectly case-sensitive email validation in `REMOTE_USER`
  authentication.
- Fixed search results for `has:image`.
- Fixed ability to adjust "Who can post on the stream" configuration.
- Fixed display of "Permission [to post] will be granted in n days"
  for n > 365.
- Support providing `nginx_listen_port` setting in conjunction with
  `http_only` in `zulip.conf`.
- Improved upgrade documentation.
- Removed internal ID lists which could leak into the events API.

### Zulip Server 3.1

_Released 2020-07-30_

- Removed unused `short_name` field from the User model. This field
  had no purpose and could leak the local part of email addresses
  when email address visibility was restricted.
- Fixed a bug where loading spinners would sometimes not be displayed.
- Fixed incoming email gateway exception with unstructured headers.
- Fixed AlertWords not being included in data import/export.
- Fixed Twitter previews not including a clear link to the tweet.
- Fixed compose box incorrectly opening after uploading a file in a
  message edit widget.
- Fixed exception in SAML integration with encrypted assertions.
- Fixed an analytics migration bug that could cause upgrading from 2.x
  releases to fail.
- Added a Thinkst Canary integration (and renamed the old one, which
  was actually an integration for canarytokens.org).
- Reformatted the frontend codebase using prettier. This change was
  included in this maintenance release to ensure backporting patches
  from `main` remains easy.

### Zulip Server 3.0

_Released 2020-07-16_

#### Highlights

- Added support for Ubuntu 20.04 Focal. This release drops support
  for Ubuntu 16.04 Xenial and Debian 9 Stretch.
- Redesigned the top navbar/search area to be much cleaner and show
  useful data like subscriber counts and stream descriptions in
  default views.
- Added a new "Recent topics" widget, which lets one browse recent
  and ongoing conversations at a glance. We expect this widget to
  replace "All messages" as the default view in Zulip in the
  next major release.
- Redesigned "Notification settings" to have an intuitive table
  format and display any individual streams with non-default settings.
- Added support for moving topics between streams. This was by far
  Zulip's most-requested feature.
- Added automatic theme detection using prefers-color-scheme.
- Added support for GitLab and Sign in with Apple authentication.
- Added an organization setting controlling who can use private messages.
- Added support for default stream groups, which allow organizations
  to offer options of sets of streams when new users sign up.
  Currently can only be managed via the Zulip API.
- The Zulip server now sets badge counts for the iOS mobile app.
- Quote-and-reply now generates a handy link to the quoted message.
- Upgraded Django from 1.11.x to the latest LTS series, 2.2.x.
- Added integrations for ErrBit, Grafana, Thinkst Canary, and Alertmanager.
- Extended API documentation to have detailed data on most responses,
  validated against the API's actual implementation and against all
  tests in our extensive automated test suite.
- Added support for programmable message retention policies, both a
  global/default policy and policies for specific streams.
- Added a new incoming webhook API that accepts messages in the format
  used by Slack's incoming webhooks API.
- Introduced the Zulip API feature level, a concept that will greatly
  simplify the implementation of mobile, terminal, and desktop clients
  that need to talk to a wide range of supported Zulip server
  versions, as well as the [Zulip API
  changelog](https://zulip.com/api/changelog).
- Our primary official domain is now zulip.com, not zulipchat.com.

#### Upgrade notes for 3.0

- Logged in users will be logged out during this one-time upgrade to
  transition them to more secure session cookies.
- This release contains dozens of database migrations, but we don't
  anticipate any of them being particularly expensive compared to
  those in past major releases.
- Previous versions had a rare bug that made it possible to create two
  user accounts with the same email address, preventing either from
  logging in. A migration in this release adds a database constraint
  that will fix this bug. The new migration will fail if any such
  duplicate accounts already exist; you can check whether this will
  happen be running the following in a [management shell][manage-shell]:
  ```python
  from django.db.models.functions import Lower
  UserProfile.objects.all().annotate(email_lower=Lower("delivery_email"))
      .values('realm_id', 'email_lower').annotate(Count('id')).filter(id__count__gte=2)
  ```
  If the command returns any accounts, you need to address the
  duplicate accounts before upgrading. Zulip Cloud only had two
  accounts affected by this bug, so we expect the vast majority of
  installations will have none.
- This release switches Zulip to install PostgreSQL 12 from the upstream
  PostgreSQL repository by default, rather than using the default
  PostgreSQL version included with the operating system. Existing Zulip
  installations will continue to work with PostgreSQL 10; this detail is
  configured in `/etc/zulip/zulip.conf`. We have no concrete plans to
  start requiring PostgreSQL 12, though we do expect it to improve
  performance. Installations that would like to upgrade can follow
  [our new PostgreSQL upgrade guide][postgresql-upgrade].
- The format of the `JWT_AUTH_KEYS` setting has changed to include an
  [algorithms](https://pyjwt.readthedocs.io/en/latest/algorithms.html)
  list: `{"subdomain": "key"}` becomes
  `{"subdomain": {"key": "key", "algorithms": ["HS256"]}}`.
- Added a new organization owner permission above the previous
  organization administrator. All existing organization
  administrators are automatically converted into organization owners.
  Certain sensitive administrative settings are now only
  editable by organization owners.
- The changelog now has a section that makes it easy to find the
  Upgrade notes for all releases one is upgrading across.

[manage-shell]: ../production/management-commands.md#managepy-shell
[postgresql-upgrade]: ../production/upgrade.md#upgrading-postgresql

#### Full feature changelog

- Added new options in "Manage streams" to sort by stream activity or
  number of subscribers.
- Added new options to control whether the incoming email integration
  prefers converting the plain text or HTML content of an email.
- Added server support for creating an account from mobile/terminal apps.
- The Zulip desktop apps now do social authentication (Google, GitHub,
  etc.) via an external browser.
- Added support for BigBlueButton as video chat provider.
- Added support for setting an organization-wide default language for
  code blocks.
- Added an API endpoint for fetching a single user.
- Added built-in rate limiting for password authentication attempts.
- Added data export/import support for organization logo and icon.
- Added documentation for several more API endpoints.
- Added new email address visibility option hiding real email
  addresses from organization administrators in the Zulip UI.
- Added new "Mention time" Markdown feature to communicate about times
  in a time-zone-aware fashion.
- Added new "Spoiler" Markdown feature to hide text until interaction.
- Added a new API that allows the mobile/desktop/terminal apps to
  open uploaded files in an external browser that may not be logged in.
- Added several database indexes that significantly improve
  performance of common queries.
- Added an organization setting to disable the compose box video call feature.
- Added a user setting to disable sharing one's presence information
  with other users.
- Added support for IdP-initiated SSO in the SAML authentication backend.
- Added new "messages sent over time" graph on /stats.
- Added support for restricting SAML authentication to only some Zulip
  organizations.
- Added `List-Id` header to outgoing emails for simpler client filtering.
- Changed how avatar URLs are sent to clients to dramatically improve
  network performance in organizations with 10,000s of user accounts.
- Redesigned all of our avatar/image upload widgets to have a cleaner,
  simpler interface.
- Normal users can now see invitations they sent via organization settings.
- Rewrote the Zoom video call integration.
- Polished numerous subtle elements of Zulip's visual design.
- Dramatically improved the scalability of Zulip's server-to-client
  push system, improving throughput by a factor of ~4.
- Improved handling of GitHub accounts with several email addresses.
- Improved "Manage streams" UI to clearly identify personal settings
  and use pills for adding new subscribers.
- Improved Sentry, Taiga, GitHub, GitLab, Semaphore, and many other integrations.
- Improved "Muted topics" UI to show when a topic was muted.
- Improved the UI for "Drafts" and "Message edit history" widgets.
- Improved left sidebar popovers to clearly identify administrative actions.
- Rewrote substantial parts of the Zulip installer to be more robust.
- Replaced the chevron menu indicators in sidebars with vertical ellipses.
- Removed the right sidebar "Group PMs" widget. It's functionality is
  available in the left sidebar "Private messages" widget.
- Removed the Google Hangouts integration, due to Google's support for
  it being discontinued.
- Removed a limitation on editing topics of messages more than a week old.
- The Gitter data import tool now supports importing multiple Gitter
  rooms into a single Zulip organization.
- Missed-message emails and various onboarding content are now tagged
  for translation.
- Redesigned the notice about large numbers of unread messages to be
  a banner (no longer a modal) and to use a better trigger.
- Cleaned up dozens of irregularities in how the Zulip API formats
  data when returning it to clients.
- Extended stream-level settings for who can post to a stream.
- Extended GET /messages API to support a more intuitive way to
  request the first unread or latest message as the anchor.
- Muted topics will now only appear behind "more topics".
- Improved UI for picking which streams to invite new users to.
- Improved UI for reviewing one's muted topics.
- Improved UI for message edit history.
- Fixed many minor issues with Zulip's Markdown processors.
- Fixed many subtle issues with the message editing UI.
- Fixed several subtle issues with the default nginx configuration.
- Fixed minor issues with various keyboard shortcuts.
- Fixed UI bugs with Zulip's image lightbox.
- Specifying `latex` or `text` as the language for a code block now
  does LaTeX syntax highlighting (`math` remains the recommended code
  block language to render LaTeX syntax into display math).
- Fixed performance problems when adding subscribers in organizations
  with thousands of streams.
- Fixed performance issues with typeahead and presence in
  organizations with 10,000s of total users.
- Fixed guest users being added to the notifications stream
  unconditionally.
- Fixed inconsistencies in the APIs for fetching users and streams.
- Fixed several subtle bugs with local echo in rare race conditions.
- Fixed a subtle race that could result in semi-duplicate emoji reactions.
- Fixed subtle click-handler bugs with the mobile web UI.
- Improved defaults to avoid OOM kills on low RAM servers when running
  expensive tools like `webpack` or Slack import.
- Added loading indicators for scrolling downwards and fixed several
  subtle bugs with the message feed discovered as a result.
- Added a migration to fix invalid analytics data resulting from a
  missing unique constraint (and then add the constraint).
- Dramatically simplified the process for adding a new authentication backend.
- Added webhook support for AnsibleTower 9.x.y.
- Essentially rewrote our API documentation using the OpenAPI format,
  with extensive validation to ensure its accuracy as we modify the API.
- Removed New User Bot and Feedback Bot. Messages they had sent are
  migrated to have been sent by Notification Bot.
- Removed the "pointer" message ID from Zulip, a legacy concept dating
  to 2012 that predated tracking unread messages in Zulip and has
  largely resulted in unexpected behavior for the last few years.
- Reduced visual size of emoji in message bodies for a cleaner look.
- Replaced file upload frontend with one supporting chunked upload.
  We expect this to enable uploading much larger files using Zulip in
  future releases.
- Improved error messages when trying to invite a user with an
  existing, deactivated, account.
- Improved server logging format to refer to users with
  `userid@subdomain` rather than referencing email addresses.
- Improved warnings when sending wildcard mentions to large streams.
- Migrated the frontend codebase to use native ES6 data structures.
- Migrated settings for notifications streams to our standard UX model.
- Various security hardening changes suggested by the PySA static analyzer.
- Modernized the codebase to use many Python 3.6 and ES6 patterns.
- Integrated isort, a tool which ensures that our Python codebase
  has clean, sorted import statements.
- Integrated PySA, a tool for detecting security bugs in Python
  codebases using the type-checker.
- Integrated semgrep, and migrated several regular expression based
  linter rules to use its Python syntax-aware parser.
- Added tooling to automatically generate all screenshots in
  integration docs.
- Restructured the backend for Zulip's system administrator level
  settings system to be more maintainable.
- This release largely completes the SCSS refactoring of the codebase.
- Replaced our CasperJS frontend integration test system with Puppeteer.
- Extracted the typeahead and Markdown libraries for reuse in the
  mobile apps.
- Removed the legacy websockets-based system for sending messages. This
  system was always a hack, was only ever used for one endpoint, and
  did not provide a measurable latency benefit over HTTP/2.

## Zulip Server 2.1.x series

### Zulip Server 2.1.8

_Released 2021-08-11_

- Fixed possible `0257_fix_has_link_attribute.py` database migration
  failure, which would cause errors during the upgrade process.

### Zulip Server 2.1.7

_Released 2020-06-25_

- CVE-2020-15070: Fix privilege escalation vulnerability with custom
  profile fields and direct write access to Zulip's PostgreSQL database.
- Changed default memcached authentication username to zulip@localhost,
  fixing authentication problems when servers change their hostname.

### Zulip Server 2.1.6

_Released 2020-06-17_

- Fixed use of Python 3.6+ syntax in 2.1.5 release that prevented
  installation on Ubuntu 16.04.

### Zulip Server 2.1.5

_Released 2020-06-16_

- CVE-2020-12759: Fix reflected XSS vulnerability in Dropbox webhook.
- CVE-2020-14194: Prevent reverse tabnapping via topic header links.
- CVE-2020-14215: Fixed use of invitation role data from expired
  invitations on signup via external authentication methods.
- CVE-2020-14215: Fixed buggy `0198_preregistrationuser_invited_as`
  database migration from the 2.0.0-rc1 release, which incorrectly added
  the administrator role to invitations.
- CVE-2020-14215: Added migration to clear the administrator role from
  any invitation objects already corrupted by the buggy version of the
  `0198_preregistrationuser_invited_as` migration.
- Fixed missing quoting of certain attributes in HTML templates.
- Allow /etc/zulip to be a symlink (for [docker-zulip][docker-zulip]).
- Disabled access from insecure Zulip Desktop releases below version 5.2.0.
- Adjusted Slack import documentation to help administrators avoid OOM
  kills when doing Slack import on low-RAM systems.
- Fixed a race condition fetching users' personal API keys.
- Fixed a few bugs with Slack data import.

#### Upgrade notes for 2.1.5

Administrators of servers originally installed with Zulip 1.9 or older
should audit for unexpected [organization
administrators][audit-org-admin] following this upgrade, as it is
possible CVE-2020-14215 caused a user to incorrectly join as an
organization administrator in the past. See the release blog post for
details.

[audit-org-admin]: https://zulip.com/help/change-a-users-role

### Zulip Server 2.1.4

_Released 2020-04-16_

- Fixed a regression in 2.1.3 that impacted creating the very first
  organization via our data import tools.
- Remove the old `tsearch_extras` PostgreSQL extension, which was causing
  an exception restoring backups on fresh Zulip servers that had been
  generated on systems that had been upgraded from older Zulip releases.
- Removed fetching GitHub contributor data from static asset build
  process. This makes `upgrade-zulip-from-git` much more reliable.
- Updated translation data from Transifex.
- Support for Ubuntu 16.04 Xenial and Debian 9 Stretch is now deprecated.

### Zulip Server 2.1.3

_Released 2020-04-01_

- CVE-2020-9444: Prevent reverse tabnapping attacks.
- CVE-2020-9445: Remove unused and insecure modal_link feature.
- CVE-2020-10935: Fix XSS vulnerability in local link rewriting.
- Blocked access from Zulip Desktop versions below 5.0.0. This
  behavior can be adjusted by editing `DESKTOP_*_VERSION`
  in `/home/zulip/deployments/current/version.py`.
- Restructured server initialization to simplify initialization of
  Docker containers (eliminating common classes of user error).
- Removed buggy feedback bot (`ENABLE_FEEDBACK`).
- Migrated GitHub authentication to use the current encoding.
- Fixed support for restoring a backup on a different minor release
  (in the common case they have the same database schema).
- Fixed restoring backups with memcached authentication enabled.
- Fixed preview content (preheaders) for many emails.
- Fixed buggy text in missed-message emails with PM content disabled.
- Fixed buggy loading spinner in "emoji format" widget.
- Fixed sorting and filtering users in organization settings.
- Fixed handling of links to deleted streams.
- Fixed check-rabbitmq-consumers monitoring.
- Fixed copy-to-clipboard button for outgoing webhook bots.
- Fixed logging spam from soft_deactivation cron job.
- Fixed email integration handling of emails with nested MIME structure.
- Fixed Unicode bugs in incoming email integration.
- Fixed error handling for Slack data import.
- Fixed incoming webhook support for AWX 9.x.y.
- Fixed a couple missing translation tags.
- Fixed "User groups" settings UI bug for administrators.
- Fixed data import tool to reset resource limits after importing
  data from a free plan organization on zulip.com.
- Changed the SAML default signature algorithm to SHA-256, overriding
  the SHA-1 default used by python3-saml.

### Zulip Server 2.1.2

_Released 2020-01-16_

- Corrected fix for CVE-2019-19775 (the original fix was affected by
  an unfixed security bug in Python's urllib, CVE-2015-2104).
- Migrated data for handling replies to missed-message emails from
  semi-persistent Redis to the fully persistent database.
- Added authentication for Redis and memcached even in configurations
  where these are running on localhost, for add hardening against
  attacks from malicious processes running on the Zulip server.
- Improved logging for misconfigurations of LDAP authentication.
- Improved error handling for invalid LDAP configurations.
- Improved error tracebacks for invalid memcached keys.
- Fixed support for using LDAP with email address visibility
  limited to administrators.
- Fixed styling of complex markup within /me messages.
- Fixed left sidebar duplicating some group private message threads.
- Fixed the "Mentions" narrow being unable to mark messages as read.
- Fixed error handling bug preventing rerunning the installer.
- Fixed a few minor issues with migrations for upgrading from 2.0.x.

### Zulip Server 2.1.1

_Released 2019-12-13_

- Fixed upgrading to 2.1.x with the LDAP integration enabled in a
  configuration where `AUTH_LDAP_REVERSE_EMAIL_SEARCH` is newly
  required, but is not yet set.
- Reimplemented `--postgres-missing-dictionaries` installer option,
  used with our new support for a DBaaS managed database.
- Improved documentation for `AUTH_LDAP_REVERSE_EMAIL_SEARCH`.

### Zulip Server 2.1.0

_Released 2019-12-12_

#### Highlights

- Added support for Debian 10. Removed support for EOL Ubuntu 14.04.
- Added support for SAML authentication.
- Removed our dependency on `tsearch_extras`, making it possible to
  run a production Zulip server against any PostgreSQL database
  (including those where one cannot install extensions, like Amazon RDS).
- Significantly improved the email->Zulip gateway, and added [nice
  setup documentation](../production/email-gateway.md). It now
  should be possible to subscribe a Zulip stream to an email list and
  have a good experience.
- Added an option for hiding access to user email addresses from
  other users. While counterproductive for most corporate
  communities, for open source projects and other volunteer
  organizations, this can be a critical anti-spam feature.
- Added a new setting controlling which unread messages are counted in
  the favicon, title, and desktop app.
- Support for showing inline previews of linked webpages has moved
  from alpha to beta. See the upgrade notes below for some changes in
  how it is configured.
- Added support for importing an organization from Mattermost (similar
  to existing Slack/HipChat/Gitter import tools). Slack import now
  supports importing data only included in corporate exports,
  including private messages and shared channels.
- Added Markdown support and typeahead for mentioning topics.
- Email notifications have been completely redesigned with a minimal,
  readable style inspired by GitHub's email notifications.
- We merged significant preparatory work for supporting RHEL/CentOS in
  production. We're now interested in beta testers for this feature.
- Reorganized Zulip's documentation for sysadmins, and added [new
  documentation](../production/modify.md)
  on maintaining a fork of Zulip.
- Added new `streams:public` search operator that searches the public
  history of all streams in the organization (even before you joined).
- Added support for sending email and mobile push notifications for
  wildcard mentions (@all and @everyone). Previously, they only
  triggered desktop notifications; now, that's configurable.

#### Upgrade notes for 2.1.0

- The defaults for Zulip's now beta inline URL preview setting have changed.
  Previously, the server-level `INLINE_URL_EMBED_PREVIEW` setting was
  disabled, and organization-level setting was enabled. Now, the
  server-level setting is enabled by default, and the organization-level
  setting is disabled. As a result, organization administrators can
  configure this feature entirely in the UI. However, servers that had
  previously [enabled previews of linked
  websites](https://zulip.com/help/allow-image-link-previews) will
  lose the setting and need to re-enable it.
- We rewrote the Google authentication backend to use the
  `python-social-auth` system we use for other third-party
  authentication systems. For this release, the old variable names
  still work, but users should update the following setting names in
  their configuration as we will desupport the old names in a future
  release:
  - In `/etc/zulip/zulip-secrets.conf`, `google_oauth2_client_secret`
    is now called with `social_auth_google_secret`.
  - In `/etc/zulip/settings.py`, `GOOGLE_OAUTH2_CLIENT_ID` should be
    replaced with `SOCIAL_AUTH_GOOGLE_KEY`.
  - In `/etc/zulip/settings.py`, `GoogleMobileOauth2Backend` should
    be replaced with called `GoogleAuthBackend`.
- Installations using Zulip's LDAP integration without
  `LDAP_APPEND_DOMAIN` will need to configure two new settings telling
  Zulip how to look up a user in LDAP given their email address:
  `AUTH_LDAP_REVERSE_EMAIL_SEARCH` and `AUTH_LDAP_USERNAME_ATTR`. See
  the [LDAP configuration
  instructions](../production/authentication-methods.md#ldap-including-active-directory)
  for details. You can use the usual `manage.py query_ldap` method to
  verify whether your configuration is working correctly.
- The Zulip web and desktop apps have been converted to directly count
  all unread messages, replacing an old system that just counted the
  (recent) messages fully fetched by the web app. This one-time
  transition may cause some users to notice old messages that were
  sent months or years ago "just became unread". What actually
  happened is the user never read these messages, and the Zulip web app
  was not displaying that. Generally, the fix is for users to simply
  mark those messages as read as usual.
- Previous versions of Zulip's installer would generate the secrets
  `local_database_password` and `initial_password_salt`. These
  secrets don't do anything, as they only modify behavior of a Zulip
  development environment. We recommend deleting those lines from
  `/etc/zulip/zulip-secrets.conf` when you upgrade to avoid confusion.
- This release has a particularly expensive database migration,
  changing the `UserMessage.id` field from an `int` to a `bigint` to
  support more than 2 billion message deliveries on a Zulip server.
  It runs in 2 phases: A first migration that doesn't require the
  server to be down (which took about 4 hours to process the 250M rows
  on chat.zulip.org, and a second migration that does require downtime
  (which took about 60 seconds for chat.zulip.org). You can check the
  number of rows for your server with `UserMessage.objects.count()`.

  We expect that most Zulip servers can happily just use the normal
  upgrade process with a few minutes of downtime. Zulip servers with
  over 1M messages may want to first upgrade to [this
  commit](https://github.com/zulip/zulip/commit/b008515d63841e1c0a16ad868d3d67be3bfc20ca)
  using `upgrade-zulip-from-git`, following the instructions to avoid
  downtime, and then upgrade to the new release.

#### Full feature changelog

- Added sortable columns to all tables in settings pages.
- Added web app support for self-service public data exports.
- Added 'e' keyboard shortcut for editing currently selected message.
- Added support for unstarring all starred messages.
- Added support for using `|` as an OR operator in sidebar search features.
- Added direct download links for Android APKs to our /apps/ page.
- Added a responsive design for our /integrations/ pages.
- Added typeahead for slash commands.
- Added more expansive moderation settings for who can create streams,
  edit user groups, or invite other users to join streams.
- Added new Bitbucket Server, Buildbot, Harbor, Gitea and Redmine integrations.
- Added proper open graph tags for linking to a Zulip organization.
- Added organization setting to disable users uploading new avatars
  (for use with LDAP synchronization).
- Added support for completely disabling the file upload feature.
- Added a new "external account" custom profile field type, making it
  convenient to link to profiles on GitHub, Twitter, and other tools.
- Added support for choosing which email address to use in GitHub auth.
- Added a new setting to control whether inactive streams are demoted.
- Added web app support for new desktop app features: inline reply
  from notifications, and detecting user presence from OS APIs.
- Added Markdown support for headings, implemented using `# heading`,
  and removed several other unnecessary differences from CommonMark.
- Added local echo when editing messages for a more responsive experience.
- Changes to global notification settings for stream messages now
  affect existing subscriptions where the user had not explicitly
  changed the notification settings, as expected.
- The default setting value is now to send mobile push notifications
  if the user was recently online.
- Fixed issues with positioning and marking messages as read when
  doing a search where some results are unread messages.
- The private messages widget shows much deeper history of private
  message conversations in a scrollable widget (1K PMs of history).
- When there are dozens of unread topics, topic lists in the left
  sidebar now show at most 8 topics, with the rest behind "more topics".
- New users now see their most recent 20 messages as unread, to
  provide a better onboarding experience.
- Redesigned the in-app "keyboard shortcuts" popover to be more usable.
- Redesigned the interactions on several settings pages.
- Significantly improved the visual spacing around bulleted lists,
  blockquotes, and code blocks in Zulip's message feed.
- Extended buttons to visit links in topics to all URLs, not just
  URLs added by a linkifier.
- Extended several integrations to cover more events and fix bugs, and
  rewrote formatting for dozens of integraitons for cleaner punctuation.
- The beta "weekly digest emails" feature is again available as an
  organization-level configuration option, after several improvements.
- The administrative UI for managing bots now nicely links to the
  bot's owner.
- Restructured "private messages" widget to have a cleaner design.
- Significantly improved performance of the backend Markdown processor.
- Significantly improved Help Center documentation of dozens of features.
- Simplified and internationalized some notification bot messages.
- The compose box placeholder now shows users active status.
- Clicking the "EDITED" text on a message now pops message edit history.
- Adjusted the default streams in new realms to be easier to
  understand for new users.
- Improved default nginx TLS settings for stronger security.
- Improved UI of administrative user management UI.
- Improved error messages for various classes of invalid searches.
- Improved styling of both Markdown unordered and numbered lists.
- Compose typeahead now autofills stream field if only subscribed to
  one stream.
- Bot users can now post to announcement-only streams if their owners
  can (this preserves the pre-existing security model).
- User full names now must use characters valid in an email from line.
- Settings pages that normal users cannot modify are now hidden by default.
- The `has:link`, `has:attachment`, and `has:image` search keywords
  have been redesigned to correctly handle corner cases like links in
  code blocks.
- Replaced title attributes with nice tooltips in the message feed and
  buddy list.
- Fixed incorrect caching settings for the Zulip API, which could result
  in browsers appearing to display old content or remark messages unread.
- Fixed a bug that prevented sending mobile push notifications when the
  user was recently online via the mobile app.
- Fixed buggy handling of LaTeX in quote-and-reply.
- Fixed buggy rendering of bulleted lists inside blockquotes.
- Fixed several bugs with CORS in the nginx configuration.
- Fixed error message for GitHub login attempts with a deactivated account.
- Fixed email gateway issues with non-Latin characters in stream names.
- Fixed endless re-synchronization of LDAP user avatars (which
  could cause user-visible performance issues for desktop/web clients).
- Fixed all known bugs with advanced LDAP data synchronization.
- Fixed numbered list handling of blank lines between blocks.
- Fixed performance issues that made users soft-deactivated for over a
  year unable to return to the app.
- Fixed missing -X GET/POST parameters in API docs curl examples. The
  API documentation for curl examples is now automatically generated
  with automated tests for the examples to prevent future similar bugs.
- Fixed multi-line /me messages only working for the sender.
- Fixed password strength meter not updating on paste.
- Fixed numerous errors and omissions in the API documentation. Added
  a test suite comparing the API documentation to the implementation.
- Fixed copy/paste of blocks of messages in Firefox.
- Fixed problems with exception reporting when memcached is down.
- Fixed pinned streams being incorrectly displayed as inactive.
- Fixed password reset page CSS for desktop app.
- Fixed "more topics" appearing for new streams, where we can be
  confident we already have all the topics cached in the browser.
- Fixed some subtle bugs with event queues and message editing.
- Fixed real-time sync for reactions and message edits on a message
  sent to a private stream with shared history before the current user
  joined that stream.
- Fixed several subtle real-time sync issues with "stream settings".
- Fixed a few subtle Markdown processor bugs involving emoji.
- Fixed several issues where linkifiers validation was overly restrictive.
- Fixed several rare/minor UI consistency issues in the left sidebar.
- Fixed issues involving saving a message edit before file upload completes.
- Fixed issues with pasting images into the compose box from Safari.
- Fixed email gateway bot being created with incorrectly cached permissions.
- Fixed guest users seeing UI widgets they can't use.
- Fixed several issues with click handlers incorrectly closing compose.
- Fixed buggy behavior of /me messages not ending with a paragraph.
- Fixed several major UI issues with the mobile web app.
- Fixed HTML styling when copy-pasting content out of Zulip's night theme.
- Fixed obscure traceback with Virtualenv 16.0.0 unexpectedly installed.
- Added a new visual tool for testing webhook integrations.
- Rewrote the Google authentication backend to use python-social-auth,
  removing Zulip's original 2013-era SSO authentication backend.
- The `/server_settings` API now advertises supported authentication
  methods alongside details on how to render login/registration buttons.
- Rewrote HTML/CSS markup for various core components to be more
  easily modified.
- Removed the legacy static asset pipeline; everything now uses webpack.
- Renamed the system bot Zulip realm to "zulipinternal" (was "zulip").
- Switched our scrollbars to use simplebar, fixing many subtle
  scrollbar-related bugs in the process.
- Enabled webpack code splitting and deduplication.
- Started migrating our frontend codebase to TypeScript.

## Zulip Server 2.0.x series

### Zulip Server 2.0.8

_Released 2019-12-12_

- CVE-2019-19775: Close open redirect in thumbnail view.

### Zulip Server 2.0.7

_Released 2019-11-21_

- CVE-2019-18933: Fix insecure account creation via social authentication.
- Added backend enforcement of zxcvbn password strength checks.

### Zulip Server 2.0.6

_Released 2019-09-23_

- Updated signing keys for the PGroonga repository for Debian 9.
- Fixed creation of linkifiers with URLs containing &.
- Fixed a subtle bug that could cause the message list to suddenly
  scroll up in certain rare race conditions.

### Zulip Server 2.0.5

_Released 2019-09-11_

- CVE-2019-16215: Fix DoS vulnerability in Markdown LINK_RE.
- CVE-2019-16216: Fix MIME type validation.
- Fixed email gateway postfix configuration for Ubuntu 18.04.
- Fixed support for hidden_by_limit messages in Slack import.
- Fixed confusing output from the `knight` management command.

### Zulip Server 2.0.4

_Released 2019-06-29_

- Fixed several configuration-dependent bugs that caused
  restore-backup to crash.
- Fixed a table layout bug in "deactivated users" settings.
- Fixed an exception when administrators edited bot users when custom
  profile fields were configured in the organization.
- Fixed a bug enabling the PGRoonga search backend with older PostgreSQL.
- Fixed getting personal API key when passwords are disabled.

### Zulip Server 2.0.3

_Released 2019-04-23_

- Added documentation for upgrading the underlying OS version.
- Made uwsgi buffer size configurable (relevant for sites putting
  Zulip behind a proxy that adds many HTTP headers).
- Fixed loss of LaTeX syntax inside quote-and-reply.
- Fixed virtualenv-related bug when upgrading Zulip when the system
  virtualenv package is 16.0.0 or newer (no supported platform has
  such a version by default, but one can install it manually).
- Fixed `manage.py query_ldap` test tool (broken in 2.0.2).
- Fixed several bugs in new backup and restore tools.
- Fixed minor bugs with YouTube previews.

### Zulip Server 2.0.2

_Released 2019-03-15_

- Fixed a regression in the Puppet configuration for S3 upload backend
  introduced in 2.0.1.
- Fixed a too-fast fade for "Saved" in organization settings.
- Fixed a white flash when loading a browser in night mode.
- Fixed a few bugs in new LDAP synchronization features.
- Fixed a buggy validator for custom stream colors.
- Fixed a confusing "Subscribe" button appearing for guest users.
- Updated translations, including a new Italian translation.

### Zulip Server 2.0.1

_Released 2019-03-04_

- Fixed handling of uploaded file routing on Ubuntu 14.04.
- Fixed buggy behavior of branding logos in night theme.
- Fixed handling of deployment directories being owned by root.
- The styling of "unavailable" status icons is now less prominent.
- The "deactivated realm" error page now auto-refreshes, to handle
  realm reactivation.
- Updated documentation to avoid recommending realm deactivation as
  a preferred approach to prepare for backups.
- Added support for using multiple organizations with same LDAP
  backend configuration.

### Zulip Server 2.0.0

_Released 2019-03-01_

#### Highlights

- Added automation for synchronizing user avatars, custom profile
  fields, disabled status, and more from LDAP/active directory.
- Added support for explicitly setting oneself as "away" and "user
  status" messages.
- Added a built-in /poll slash command for lightweight polls.
- Added experimental support for using Zoom as the video chat
  provider. We now support Jitsi, Google Hangouts, and Zoom.
- Added support for branding the top-left corner of the logged in app
  with an organization's logo.
- Zulip's "Guest users" feature is no longer experimental.
- The HipChat/Stride data import tool is no longer experimental.
  Our HipChat and Slack import tools are now well-tested with millions
  of messages, 10,000s of users, and 100,000s of uploaded files.
- Added a built-in tool for backups and restoration.
- Deprecated support for Ubuntu 14.04. Zulip 2.0.x will continue to
  support Ubuntu 14.04, but Zulip 2.1.0 will remove support for
  installing on Ubuntu 14.04.

#### Upgrade notes for 2.0.0

- This release adds support for submitting basic usage statistics to
  help the Zulip core team. This feature can be enabled only if a server
  is using the [Mobile Push Notification Service][mobile-push],
  and is enabled by default in that case. To disable it, set
  `SUBMIT_USAGE_STATISTICS = False` in `/etc/zulip/settings.py`.

#### Full feature changelog

- Added support for CentOS 7 in the development environment
  provisioning process. This is an important step towards production
  CentOS/RHEL 7 support.
- Added a new invitation workflow with reusable links.
- Added a new Azure Active Directory authentication integration.
  New authentication backends supported by python-social-auth can now be
  added with just a few dozen lines of code.
- Added API documentation for user groups and custom emoji.
- Administrators can now easily delete a topic.
- Added display of a user's role (administrator, guest, etc.) in
  various relevant places.
- Added support for sending "topic" rather than the legacy "subject"
  for the topic in most API endpoints.
- Added helpful notifications for some common webhook
  misconfigurations.
- Added organization setting to control whether users are allowed to
  include message content in missed-message emails (for compliance).
- Added an automated notification when streams are renamed.
- Added support for changing the default notification sound.
- Added Ctrl+. shortcut for narrowing to current compose recipient.
- Added icons to indicate which "organization settings" tabs are
  available to regular users.
- Added a tool for migrating from S3 to the local file uploads backend.
- Added protocol for communicating version incompatibility to mobile apps.
- Added support for copying avatar and other profile data when
  creating a second account on a Zulip server with a given email address.
- Added /digest endpoint for viewing the current digest email on the web.
- Added alert for when a user sends a message when scrolled too far up.
- Added internationalization for outgoing emails.
- Added a Review Board integration, and improved numerous existing integrations.
- Added support for multi-line messages for the /me feature.
- Added Markdown rendering of text when displaying custom profile fields.
- Added "silent mentions" syntax (`@_**Tim Abbott**`), which show
  visually, but don't trigger a notification to the target user.
- Added support for using lightbox in compose preview.
- Changes in date no longer force a repeated recipient bar. This
  fixes a common source of confusion for new users.
- Suppressed notifications when quoting a message mentioning yourself.
- Message editing now has the compose widgets for emoji, video calls, etc.
- Message editing now has a Markdown preview feature just like compose.
- Message editing now uses same "Enter-sends" behavior as compose.
- Organization administrators can now edit users' custom profile fields.
- Optimized performance of data import from Slack, HipChat, etc.
- Improved "new user" emails to clearly indicator login details.
- Improved the UI for "drafts" and "message edit history".
- Improved linkifier handling of languages with character alphabets.
- Improved accessibility of emoji rendering in messages bodies.
- Eliminated UI lag when using "Quote and reply".
- Expanded production documentation for more unusual deployment options.
- Expanded set of characters allowed in custom linkifiers.
- Optimized development provisioning; now takes 2s in the no-op case.
- Zulip's Help Center now has nicely generated open graph tags.
- Fixed missing API authentication headers for mobile file access.
- Fixed various select and copy-paste issues.
- Fixed various back button bugs in settings UI.
- Fixed various mobile web visual issues.
- Fixed unnecessary resizing of animated custom emoji.
- Fixed several performance issues for organizations with 1000s of streams.
- Fixed various error handling bugs sending push notifications.
- Fixed handling of diacritics in user-mention typeahead.
- Fixed several bugs with importing data into Zulip's S3 backend.
- Fixed display of full recipients list in "private messages" hover.
- Fixed bugs involving muting and renamed streams.
- Fixed soft-deactivation performance issues with many thousands of users.
- Countless behind-the-scenes improvements to Zulip's codebase,
  tooling, automated tests, error handling, and APIs.

## Zulip Server 1.9.x series

### Zulip Server 1.9.2

_Released 2019-01-29_

This release migrates Zulip off a deprecated Google+ API (necessary
for Google authentication to continue working past March 7), and
contains a few bug fixes for the installer and Slack import. It has
minimal changes for existing servers not using Google authentication.

- Updated the Google auth integration to stop using a deprecated and
  soon-to-be-removed Google+ authentication API.
- Improved installer error messages for common configuration problems.
- Fixed several bugs in Slack, Gitter, and HipChat import tools.
- Fixed a subtle bug in garbage-collection of the node_modules cache.
- Optimized performance of Slack import for organizations with
  thousands of users.

### Zulip Server 1.9.1

_Released 2018-11-30_

This release is primarily intended to improve the experience for new
Zulip installations; it has minimal changes for existing servers.

- Added support for getting multi-domain certificates with setup-certbot.
- Improved various installer error messages and sections of the
  installation documentation to help avoid for common mistakes.
- The Google auth integration now always offers an account chooser.
- Fixed buggy handling of avatars in Slack import.
- Fixed nginx configuration for mobile API authentication to access uploads.
- Updated translation data, including significant new Italian strings.

### Zulip Server 1.9.0

_Released 2018-11-07_

#### Highlights

- Support for Ubuntu 18.04 and Debian 9 (our first non-Ubuntu
  platform!). We expect to deprecate support for installing a new
  Zulip server on Ubuntu 14.04 in the coming months, in preparation
  for Ubuntu 14.04’s end-of-life in April 2019.
- New data import tools for HipChat and Gitter. The Slack importer
  is now out of beta.
- Zulip Python process startup time is about 30% faster; this effort
  resulted in upstream contributions to fix significant performance
  bugs in django-bitfield, libthumbor, and pika.
- You can now configure custom (organization-specific) fields for user
  profiles; Zulip can now serve as your organization’s employee
  directory.
- Zulip now supports using Google Hangouts instead of Jitsi as the
  video chat provider.
- Users can now configure email and mobile push notifications for
  all messages in a stream (useful for low-traffic
  streams/organizations), not just for messages mentioning them.
- New [stream settings](https://zulip.com/help/stream-permissions)
  control whether private stream subscribers can access history
  from before they joined, and allow configuring streams to only
  allow administrators to post.
- Zulip now has experimental support for guest users (intended
  for use cases like contractors who the organization only wants
  to have access to a few streams).
- New native integrations for Ansible Tower, Appveyor, Clubhouse,
  Netlify, and Zabbix; Zulip now has over 100 native integrations (in
  addition to hundreds more available via Zapier and IFTTT).
- New translations for Ukrainian, Portuguese, Indonesian, Dutch, and
  Finnish. Zulip now has complete or nearly-complete translations
  for German, Spanish, French, Portuguese, Russian, Ukrainian,
  Czech, Finnish, and Turkish. Partial translations for Chinese,
  Dutch, Korean, Polish, Japanese, and Indonesian cover the majority
  of the total strings in the project.

#### Upgrade notes for 1.9.0

- Zulip 1.9 contains a significant database migration that can take
  several minutes to run. The upgrade process automatically minimizes
  disruption by running this migration first, before beginning the
  user-facing downtime. However, if you'd like to watch the downtime
  phase of the upgrade closely, we recommend
  running them first manually
  as well as the usual trick of doing an apt upgrade first.

#### Full feature changelog

- Added an organization setting for message deletion time limits.
- Added an organization setting to control who can edit topics.
- Added Ctrl+K keyboard shortcut for getting to search (same as /, but
  works even when you're inside compose).
- Renamed the hotkey for starring a message to Ctrl+S.
- Added the new `SOCIAL_AUTH_SUBDOMAIN` setting, which all servers using
  both GitHub authentication and hosting multiple Zulip organizations
  should set (see [the docs for details](../production/multiple-organizations.md#authentication)).
- Added automatic thumbnailing of images, powered by thumbor. The new
  THUMBOR_URL setting controls this feature; it is disabled by default
  in this release, because the mobile apps don't support it yet.
- Added documentation on alternative production deployment options.
- Added Gitter and HipChat data import tools.
- Added support for using both LDAPAuthBackend and EmailAuthBackend.
- Added support for rendering message content written in right-to-left
  languages in a right-to-left style.
- Added support for compose keyboard shortcuts in message edit UI.
- Added a fast database index supporting the "Private messages" narrow.
- Added a notification setting for whether to send "new login" emails.
- Dramatically expanded our API documentation to cover many more endpoints.
- Optimized the performance of loading Zulip in an organization with
  thousands of users and hundreds of bot users.
- Optimized production release tarballs to save about 40MB of size.
- Dropped support for the EmojiOne and Apple emoji sets, and added
  support for the Google modern emoji set.
- Removed the "Delete streams" administration page; one can delete
  streams directly on "Manage streams".
- Removed support code for the (long-deprecated) legacy desktop app.
- Fixed several bugs with progress bars when uploading files.
- Fixed several bugs in `manage.py register_server`.
- Fixed several minor real-time sync issues with stream settings.
- Fixed some tricky corner cases with the web app's caching model and
  narrowing to the first unread message.
- Fixed confusing intermediate states of group PMs online indicators.
- Fixed several subtle unread count corner case bugs.
- Fixed several installer issues to make it easier to Dockerize Zulip.
- Fixed several subtle issues with both the LDAP/Active Directory
  integration and its documentation, making it much easier to set up.
- Fixed several minor bugs and otherwise optimized search typeahead.
- Fixed a bad nginx configuration interaction with servers that have
  misconfigured IPv6.
- Fixed most of the caveats on the Slack data import tool.
- Fixed memcached cache size issues for organizations over 10,000 users.
- Zulip's data export system has full support for all features, and
  tests to ensure that it stays that way.
- Rewrote user documentation for dozens of integrations.
- Rewrote the GitHub authentication backend (and more generally our
  python-social-auth integration) to make it easier to add new auth methods.
- Upgraded to modern versions of most of our stale dependencies.
- Updated our CSS toolchain to support hot module reloading.
- Updated numerous pages within the /help/ site.
- We no longer require re-authing to sign up after trying to log in with
  an OAuth authentication backend (GitHub or Google).
- Made major improvements to the Help Center.
- Improved system for configuring the S3 file uploads backend.
- Improved emoji typeahead sorting.
- Improved Zulip's layout for windows with a width around 1024px.
- Improved Zulip's generic error handling behavior for webhooks.
- Improved keyboard navigation of settings and popovers.
- Renamed "realm filters" to "linkifiers", at least in the UI.
- Converted several layered-checkbox settings to clearer dropdowns.
- Cleaned up some legacy APIs still using email addresses.
- Made arrow-key navigation work within right and left sidebar search.
- Fixed performance issues of the right sidebar user list with 5000+
  user accounts on a server.
- Emails and several other onboarding strings are now tagged for
  translation.
- Optimized the performance of importing Zulip by about 30%. This
  significantly decreases the load spike when restarting a Zulip server.
- Optimized the performance of development provisioning; a no-op
  provision now completes in about 3.5s.
- Migrated our static asset pipeline to webpack.
- Our steady work on codebase quality and our automated test suite
  continues. Backend test coverage is now an incredible 98%.

## Zulip Server 1.8.x series

### Zulip Server 1.8.1

_Released 2018-05-07_

- Added an automated tool (`manage.py register_server`) to sign up for
  the [mobile push notifications service][mobile-push].
- Improved rendering of block quotes in mobile push notifications.
- Improved some installer error messages.
- Fixed several minor bugs with the new Slack import feature.
- Fixed several visual bugs with the new compose input pills.
- Fixed several minor visual bugs with night mode.
- Fixed bug with visual clipping of "g" in the left sidebar.
- Fixed an issue with the LDAP backend users' Organization Unit (OU)
  being cached, resulting in trouble logging in after a user was moved
  between OUs.
- Fixed a couple subtle bugs with muting.

### Zulip Server 1.8.0

_Released 2018-04-17_

#### Highlights

- Dramatically simplified the server installation process; it's now possible
  to install Zulip without first setting up outgoing email.
- Added experimental support for importing an organization's history
  from Slack.
- Added a new "night mode" theme for dark environments.
- Added a video call integration powered by Jitsi.
- Lots of visual polish improvements.
- Countless small bugfixes both in the backend and the UI.

**Security and privacy:**

- Several important security fixes since 1.7.0, which were released
  already in 1.7.1 and 1.7.2.
- The security model for private streams has changed. Now
  organization administrators can remove users, edit descriptions, and
  rename private streams they are not subscribed to. See Zulip's
  security model documentation for details.
- On Ubuntu 16.04, the local uploads backend now does the same security
  checks that the S3 backend did before serving files to users.
  Ubuntu 14.04's version of nginx is too old to support this and so
  the legacy model is the default; we recommend upgrading.
- Added an organization setting to limit creation of bots.
- Refactored the authentication backends codebase to be much easier to
  verify.
- Added a user setting to control whether email notifications include
  message content (or just the fact that there are new messages).

**Visual and UI:**

- Added a user setting to translate emoticons/smileys to emoji.
- Added a user setting to choose the emoji set used in Zulip: Google,
  Twitter, Apple, or Emoji One.
- Expanded setting for displaying emoji as text to cover all display
  settings (previously only affected reactions).
- Overhauled our settings system to eliminate the old "save changes"
  button system.
- Redesigned the "uploaded files" UI.
- Redesigned the "account settings" UI.
- Redesigned error pages for the various email confirmation flows.
- Our emoji now display at full resolution on retina displays.
- Improved placement of text when inserting emoji via picker.
- Improved the descriptions and UI for many settings.
- Improved visual design of the help center (/help/).

**Core chat experience:**

- Added support for mentioning groups of users.
- Added a setting to allow users to delete their messages.
- Added support for uploading files in the message-edit UI.
- Redesigned the compose are for private messages to use pretty pills
  rather than raw email addresses to display recipients.
- Added new Ctrl+B, Ctrl+I, Ctrl+L compose shortcuts for inserting
  common syntax.
- Added warning when linking to a private stream via typeahead.
- Added support for automatically-numbered Markdown lists.
- Added a big warning when posting to #announce.
- Added a notification when drafts are saved, to make them more
  discoverable.
- Added a fast local echo to emoji reactions.
- Messages containing just a link to an image (or an uploaded image)
  now don't clutter the feed with the URL: we just display the image.
- Redesigned the API for emoji reactions to support the full range of
  how emoji reactions are used.
- Fixed most of the known (mostly obscure) bugs in how messages are
  formatted in Zulip.
- Fixed "more topics" to correctly display all historical topics for
  public streams, even though from before a user subscribed.
- Added a menu item to mark all messages as read.
- Fixed image upload file pickers offering non-image files.
- Fixed some subtle bugs with full-text search and Unicode.
- Fixed bugs in the "edit history" HTML rendering process.
- Fixed popovers being closed when new messages come in.
- Fixed unexpected code blocks when using the email mirror.
- Fixed clicking on links to a narrow opening a new window.
- Fixed several subtle bugs with the email gateway system.
- Fixed layering issues with mobile Safari.
- Fixed several obscure real-time synchronization bugs.
- Fixed handling of messages with a very large HTML rendering.
- Fixed several bugs around interacting with deactivated users.
- Fixed interaction bugs with unread counts and deleting messages.
- Fixed support for replacing deactivated custom emoji.
- Fixed scrolling downwards in narrows.
- Optimized how user avatar URLs are transmitted over the wire.
- Optimized message sending performance a bit more.
- Fixed a subtle and hard-to-reproduce bug that resulted in every
  message being condensed ([More] appearing on every message).
- Improved typeahead's handling of editing an already-completed mention.
- Improved syntax for inline LaTeX to be more convenient.
- Improved syntax for permanent links to streams in Zulip.
- Improved behavior of copy-pasting a large number of messages.
- Improved handling of browser undo in compose.
- Improved saved drafts system to garbage-collect old drafts and sort
  by last modification, not creation.
- Removed the legacy "Zulip labs" autoscroll_forever setting. It was
  enabled mostly by accident.
- Removed some long-deprecated Markdown syntax for mentions.
- Added support for clicking on a mention to see a user's profile.
- Links to logged-in content in Zulip now take the user to the
  appropriate upload or view after a user logs in.
- Renamed "Home" to "All messages", to avoid users clicking on it too
  early in using Zulip.
- Added a user setting to control whether the organization's name is
  included in email subject lines.
- Fixed uploading user avatars encoded using the CMYK mode.

**User accounts and invites:**

- Added support for users in multiple realms having the same email.
- Added a display for whether the user is logged-in in logged-out
  pages.
- Added support for inviting a new user as an administrator.
- Added a new organization settings page for managing invites.
- Added rate-limiting on inviting users to join a realm (prevents spam).
- Added an organization setting to disable welcome emails to new users.
- Added an organization setting to ban disposable email addresses
  (I.e.. those from sites like mailinator.com).
- Improved the password reset flow to be less confusing if you don't
  have an account.
- Split the Notifications Stream setting in two settings, one for new
  users, the other for new streams.

**Stream subscriptions and settings:**

- Added traffic statistics (messages/week) to the "Manage streams" UI.
- Fixed numerous issues in the "stream settings" UI.
- Fixed numerous subtle bugs with the stream creation UI.
- Changes the URL scheme for stream narrows to encode the stream ID,
  so that they can be robust to streams being renamed. The change is
  backwards-compatible; existing narrow URLs still work.

**API, bots, and integrations:**

- Rewrote our API documentation to be much more friendly and
  expansive; it now covers most important endpoints, with nice examples.
- New integrations: ErrBot, GoCD, Google Code-In, Opbeat, Groove,
  Raygun, Insping, Dialogflow, Dropbox, Front, Intercom,
  Statuspage.io, Flock and Beeminder.
- Added support for embedded interactive bots.
- Added inline preview + player for Vimeo videos.
- Added new event types and fixed bugs in several webhook integrations.
- Added support for default bots to receive messages when they're
  mentioned, even if they are not subscribed.
- Added support for overriding the topic is all incoming webhook integrations.
- Incoming webhooks now send a private message to the bot owner for
  more convenient testing if a stream is not specified.
- Rewrote documentation for many integrations to use a cleaner
  numbered-list format.
- APIs for fetching messages now provide more metadata to help clients.

**Keyboard shortcuts:**

- Added new "basics" section to keyboard shortcuts documentation.
- Added a new ">" keyboard shortcut for quote-and-reply.
- Added a new "p" keyboard shortcut to jump to next unread PM thread.
- Fixed several hotkeys scope bugs.
- Changed the hotkey for compose-private-message from "C" to "x".
- Improve keyboard navigation of left and right sidebars with arrow keys.

**Mobile apps backend:**

- Added support for logging into the mobile apps with RemoteUserBackend.
- Improved mobile notifications to support narrowing when one clicks a
  mobile push notification.
- Statistics on the fraction of strings that are translated now
  include strings in the mobile apps as well.

**For server admins:**

- Added certbot support to the installer for getting certificates.
- Added support for hosting multiple domains, not all as subdomains of
  the same base domain.
- Added a new nagios check for the Zulip analytics state.
- Fixed buggy APNs logic that could cause extra exception emails.
- Fixed a missing dependency for the localhost_sso auth backend.
- Fixed subtle bugs in garbage-collection of old node_modules versions.
- Clarified instructions for server settings (especially LDAP auth).
- Added missing information on requesting user in many exception emails.
- Improved Tornado retry logic for connecting to RabbitMQ.
- Added a server setting to control whether digest emails are sent.

**For Zulip developers:**

- Migrated the codebase to use the nice Python 3 typing syntax.
- Added a new /team/ page explaining the team, with a nice
  visualization of our contributors.
- Dramatically improved organization of developer docs.
- Backend test coverage is now 95%.

#### Upgrade notes for 1.8.0

This major release has no special upgrade notes.

## Zulip Server 1.7.x series

### Zulip Server 1.7.2

_Released 2018-04-12_

This is a security release, with a handful of cherry-picked changes
since 1.7.1. All Zulip server admins are encouraged to upgrade
promptly.

- CVE-2018-9986: Fix XSS issues with frontend Markdown processor.
- CVE-2018-9987: Fix XSS issue with muting notifications.
- CVE-2018-9990: Fix XSS issue with stream names in topic typeahead.
- CVE-2018-9999: Fix XSS issue with user uploads. The fix for this
  adds a Content-Security-Policy for the `LOCAL_UPLOADS_DIR` storage
  backend for user-uploaded files.

Thanks to Suhas Sunil Gaikwad for reporting CVE-2018-9987 and w2w for
reporting CVE-2018-9986 and CVE-2018-9990.

### Zulip Server 1.7.1

_Released 2017-11-21_

This is a security release, with a handful of cherry-picked changes
since 1.7.0. All Zulip server admins are encouraged to upgrade
promptly.

This release includes fixes for the upgrade process, so server admins
running a version from before 1.7 should upgrade directly to 1.7.1.

- CVE-2017-0910: On a server with multiple realms, a vulnerability in
  the invitation system allowed an authorized user of one realm to
  create an account on any other realm.
- The Korean translation is now complete, a huge advance from almost
  nothing in 1.7.0. The French translation is now nearly complete,
  and several other languages have smaller updates.
- The installer now sets LC_ALL to a known locale, working around an
  issue where some dependencies fail to install in some locales.
- We fixed a bug in the script that runs after upgrading Zulip (so
  the fix applies when upgrading to this version), where the
  garbage-collection of old deployments sometimes wouldn't preserve
  the immediate last deployment.

### Zulip Server 1.7.0

_Released 2017-10-25_

#### Highlights

**Web**

- We’ve completely redesigned our onboarding process to explain Zulip,
  and especially topics, to new users.
- We’ve built a beautiful new emoji picker with categories, a
  showcase, and much better data. Note the clean, underscore-free
  display!
- The emails sent by Zulip are more consistent, readable, and visually
  interesting.
- Chinese (Simplified) and Japanese join Spanish, German, and Czech in
  having the user interface fully translated, in addition to partial
  translations for many other languages. We also fixed many small
  issues where strings weren’t tagged for translation.
- Many pages have been redesigned to be easier to use and visually
  cleaner, including the settings pages and the user documentation at
  /help, /integrations, and /apps.

**Mobile and Desktop support**

- Zulip Server 1.7 adds several new APIs that are critical for mobile
  app performance and that let the app track unread messages. If
  you’re using the mobile apps at all (iOS or Android), you will
  definitely want to upgrade to Zulip 1.7.
- The iOS and Android apps can receive push notifications
  (configurable, naturally) for events like PMs and @-mentions. While
  Zulip Server 1.6 has basic support for these, 1.7 brings a new,
  clearer format to notifications, and gives each user more options
  for finer-grained control.
- The new Electron desktop app is out of beta and replaces our legacy
  desktop apps.

**Backend and scaling**

- Zulip now runs exclusively on Python 3. This is the culmination of
  an 18-month migration effort. We are very excited about this!
- We’ve added an automatic "soft deactivation" process, which
  dramatically improves performance for organizations with a large
  number of inactive users, without any impact on those users’
  experience if they later come back.
- Zulip's performance at scale has improved significantly. Performance
  now scales primarily with number of active users (not total
  users). As an example, chat.zulip.org serves 400 monthly active
  users and about 3500 total users, on one VM with just 8GB of RAM and
  a CPU consistently over 90% idle.

#### Upgrade notes for 1.7.0

- Zulip 1.7 contains some significant database migrations that can
  take several minutes to run. The upgrade process automatically
  minimizes disruption by running these first, before beginning the
  user-facing downtime. However, if you'd like to watch the downtime
  phase of the upgrade closely, we recommend
  running them first manually
  as well as the usual trick of doing an apt upgrade first.

- We've removed support for an uncommon legacy deployment model where
  a Zulip server served multiple organizations on the same domain.
  Installs with multiple organizations now require each organization
  to have its own subdomain.

  This change should have no effect for the vast majority of Zulip
  servers that only have one organization. If you manage a server
  that hosts multiple organizations, you'll want to read [our guide on
  multiple organizations](../production/multiple-organizations.md).

- We simplified the configuration for our password strength checker to
  be much more intuitive. If you were using the
  `PASSWORD_MIN_ZXCVBN_QUALITY` setting,
  [it has been replaced](https://github.com/zulip/zulip/commit/a116303604e362796afa54b5d923ea5312b2ea23) by
  the more intuitive `PASSWORD_MIN_GUESSES`.

#### Full feature changelog

- Simplified the process for installing a new Zulip server, as well as
  fixing the most common road bumps and confusing error messages.
- Added a new "incoming webhook" bot type, limited to only sending
  messages into Zulip, for better security.
- Added experimental support for outgoing webhooks.
- Added support for changing the notifications stream.
- Added 'u' hotkey to show a user's profile.
- Added '-' hotkey to toggle collapsing a message.
- Added an organization setting to require topics in stream messages.
- Added an organization setting to control whether edit history is available.
- Added a confirmation dialogue when inviting many users to a new stream.
- Added new notification setting to always get push notifications on a stream.
- Added new "getting started" guides to the user documentation.
- Added support for installing a Zulip server from a Git checkout.
- Added support for mentioning a user when editing a message.
- Added Opsgenie, Google Code-In, Google Search, and xkcd integrations.
- Added support for organization administrators deleting private streams.
- Added support for using any LDAP attribute for login username.
- Added support for searching by group-pm-with.
- Added support for mentioning users when editing messages.
- Added a much prettier prompt for enabling desktop notifications.
- Added a new PHYSICAL_ADDRESS setting to be used in outgoing emails
  to support compliance with anti-spam regulations.
- Dramatically improved the search typeahead experience when using
  multiple operators.
- Improved design for /stats page and added a link to it in the gear menu.
- Improved how timestamps are displayed across the product.
- Improved the appearance of mention/compose typeahead.
- Improved lightbox to support panning and zooming on images.
- Improved "more topics" to fetch all historical topics from the server.
- Improved scrollbars across the site to look good on Windows and Linux.
- Improved visual design of stream management UI.
- Improved management of disk space, especially when deploying with
  Git frequently.
- Improve mention typeahead sort order to prioritize recent senders in
  a stream.
- Swapped the 'q' and 'w' hotkeys to better match the UI.
- Fixed most issues with the registration flow, including adding OAuth
  support for mobile and many corner case problems.
- Significantly improved sort ordering for the emoji picker.
- Fixed most accessibility errors detected by major accessibility
  checker tools.
- Extracted Zulip's Python API and bots ecosystem into its own
  repository, zulip/python-zulip-api.
- Enter hotkey now opens compose in empty narrows.
- Significantly improved performance of "starred messages" and
  "mentions" database queries through new indexes.
- Upgraded to Django 1.11.x.
- Upgraded to a more modern version of the SourceSansPro font.
- Redesigned several settings subpages to be visually cleaner.
- Redesigned Zulip's error pages to feature cute illustrations.
- Dramatically improved the user typeahead algorithm to suggest
  relevant users even in large organizations with 1000s of accounts.
- Fixed log rotation structural issues which wasted a lot of disk.
- Updated notification settings to not require a "save changes" button.
- Rewrote the documentation for almost all of our integrations to be
  much clearer and more consistent through use of Markdown and macros.
- Restructured Zulip's management commands to use a common system for
  accessing realms and users.
- Made starting editing a message you just sent not require a round trip.
- Dramatically increased test coverage of the frontend codebase.
- Dramatically improved the responsive mobile user experience.
- Changed the right sidebar search to ignore diacritics.
- Overhauled error handling in the new user registration flows.
- Fixed minor bugs in several webhook integrations.
- Fixed several local echo bugs involving mentions and line-wrapping.
- Fixed various inconsistent old-style buttons in settings pages.
- Fixed some obscure bugs with uploading files.
- Fixed issues with deactivating realm emoji.
- Fixed rendering of emoji in tweet previews.
- Fixed buggy translation caching which filled local storage.
- Fixed handling of desktop and mobile apps in new-login emails.
- Fixed caching of source repository in upgrade-zulip-from-git.
- Fixed numerous minor internationalization bugs.
- Fixed several bugs with the LDAP authentication backend.
- Fixed several corner case bugs with push notification.
- Fixed rendering of realm emoji in missed-message emails.
- Fixed various endpoints incorrectly using the PUT HTTP method.
- Fixed bugs in scrolling up using the home key repeatedly.
- Fixed a bug where private messages from multiple users could be
  included in a single missed-message email.
- Fixed issues with inconsistent visual display of @-all mentions.
- Fixed zombie process leaks on servers with <4GB of RAM.
- Fixed Markdown previews of /me messages.
- Fixed a subtle bug involving timestamps of locally echoed messages.
- Fixed the behavior of key combinations like Ctrl+Enter in the compose box.
- Worked around Google Compute Engine's default boto configuration,
  which broke Zulip (and any other app using boto).
- Zulip now will gracefully handle the PostgreSQL server being restarted.
- Optimized marking an entire topic as read.
- Switched from npm to yarn for downloading JS packages.
- Switched the function of the 'q' and 'w' search hotkeys.
- Simplified the settings for configuring senders for our emails.
- Emoji can now be typed with spaces, e.g. entering "robot face" in
  the typeahead as well as "robot_face".
- Improved title and alt text for Unicode emoji.
- Added development tools to make iterating on emails and error pages easy.
- Added backend support for multi-use invite links (no UI for creating yet).
- Added a central debugging log for attempts to send outgoing emails.
- Added a deprecation notice for the legacy QT-based desktop app.
- Removed most remaining legacy API format endpoints.
- Removed the obsolete shortname-based syntax.
- Removed the old django-guardian dependency.
- Removed several obsolete settings.
- Partially completed migration to webpack as our static asset bundler.

## Zulip Server 1.6.x and older

### Zulip Server 1.6.0

_Released 2017-06-06_

#### Highlights

- A complete visual redesign of the logged-out pages, including login,
  registration, integrations, etc.
- New visual designs for numerous UI elements, including the emoji
  picker, user profile popovers, sidebars, compose, and many more.
- A complete redesign of the Zulip settings interfaces to look a lot
  nicer and be easier to navigate.
- Organization admins can now configure the login and registration
  pages to show visitors a nice organization profile with custom text
  and images, written in Markdown.
- Massively improved performance for presence and settings pages,
  especially for very large organizations (1000+ users).
- A dozen useful new keyboard shortcuts, from editing messages to
  emoji reactions to drafts and managing streams.
- Typing notifications for private message threads.
- Users can now change their own email address.
- New saved-drafts feature.
- The server can now run on a machine with as little as 2GB of RAM.
- The new [Electron desktop app][electron-app] and new
  [React Native mobile app for iOS][ios-app] are now the recommended
  Zulip apps.
- Mobile web now works much better, especially on iOS.
- Support for sending mobile push notifications via
  [a new forwarding service][mobile-push]
- Complete translations for Spanish, German, and Czech (and
  expanded partial translations for Japanese, Chinese, French,
  Hungarian, Polish, Dutch, Russian, Bulgarian, Portuguese,
  Serbian, Malayalam, Korean, and Italian).

[mobile-push]: ../production/mobile-push-notifications.md
[electron-app]: https://github.com/zulip/zulip-desktop/releases
[ios-app]: https://itunes.apple.com/us/app/zulip/id1203036395

#### Full feature changelog

- Added Basecamp, Gogs, Greenhouse, Home Assistant, Slack, Splunk, and
  WordPress webhook integrations.
- Added LaTeX support to the Markdown processor.
- Added support for filtering branches to all Git integrations.
- Added read-only access to organization-level settings for all users.
- Added UI for managing muted topics and uploaded files.
- Added UI for displaying message edit history.
- Added support for various features needed by new mobile app.
- Added deep links for settings/subscriptions interfaces.
- Added an animation when messages are edited.
- Added support for registration with GitHub auth (not just login).
- Added tracking of uploaded file quotas.
- Added option to display emoji as their alt codes.
- Added new audit log table, to eventually support an auditing UI.
- Added several new permissions-related organization settings.
- Added new endpoint for fetching presence data, useful in employee directories.
- Added typeahead for language for syntax highlighting in code blocks.
- Added support for basic Markdown in stream descriptions.
- Added email notifications on new Zulip logins.
- Added security hardening before serving uploaded files.
- Added new PRIVACY_POLICY setting to provide a Markdown privacy policy.
- Added an icon to distinguish bot users as message senders.
- Added a command-line Slack importer tool using the API.
- Added new announcement notifications on stream creation.
- Added support for some newer Unicode emoji code points.
- Added support for users deleting realm emoji they themselves uploaded.
- Added support for organization administrators deleting messages.
- Extended data available to mobile apps to cover the entire API.
- Redesigned bots UI. Now can change owners and reactivate bots.
- Redesigned the visuals of code blocks to be prettier.
- Changed right sidebar presence UI to only show recently active users
  in large organizations. This has a huge performance benefit.
- Changed color for private messages to look better.
- Converted realm emoji to be uploaded, not links, for better robustness.
- Switched the default password hasher for new passwords to Argon2.
- Increased the paragraph spacing, making multi-paragraph.
- Improved formatting of all Git integrations.
- Improved the UI of the /stats analytics pages.
- Improved search typeahead to support group private messages.
- Improved logic for when the compose box should open/close.
- Improved lightbox to support scrolling through images.
- Improved Markdown support for bulleted lists.
- Improved copy-to-clipboard support in various places.
- Improved subject lines of missed message emails.
- Improved handling of users trying to log in with OAuth without an account.
- Improved UI of off-the-Internet errors to not be hidden in narrow windows.
- Improved rate-limiting errors to be more easily machine-readable.
- Parallelized the backend test suite; now runs 1600 tests in <30s.
- Fixed numerous bugs and performance issues with stream management.
- Fixed an issue with the fake emails assigned to bot users.
- Fixed a major performance issue in stream creation.
- Fixed numerous minor accessibility issues.
- Fixed a subtle interaction between click-to-reply and copy-paste.
- Fixed various formatting issues with /me messages.
- Fixed numerous real-time sync issues involving users changing their
  name, avatar, or email address and streams being renamed.
- Fixed numerous performance issues across the project.
- Fixed various left sidebar ordering and live-updated bugs.
- Fixed numerous bugs with the message editing widget.
- Fixed missing logging / rate limiting on browser endpoints.
- Fixed regressions in Zulip's browser state preservation on reload logic.
- Fixed support for Unicode characters in the email mirror system.
- Fixed load spikes when email mirror is receiving a lot of traffic.
- Fixed the ugly grey flicker when scrolling fast on Macs.
- Fixed previews of GitHub image URLs.
- Fixed narrowing via clicking on desktop notifications.
- Fixed Subscribed/Unsubscribed bookends appearing incorrectly.
- Eliminated the idea of a realm having a canonical domain; now
  there's simply the list of allowed domains for new users.
- Migrated avatars to a user-id-based storage setup (not email-based).
- Trailing whitespace is now stripped in code blocks, avoiding
  unnecessary scrollbars.
- Most API payloads now refer to users primarily by user ID, with
  email available for backwards-compatibility. In the future, we may
  remove email support.
- Cleaned up Zulip's supervisord configuration. A side effect is the
  names of the log files have changed for all the queue workers.
- Refactored various endpoints to use a single code path for security
  hardening.
- Removed support for the `MANDRILL_CLIENT` setting. It hadn't been
  used in years.
- Changed `NOREPLY_EMAIL_ADDRESS` setting to `Name <user@example.com>`
  format.
- Disabled the web tutorial on mobile.
- Backend test coverage is now 93%, with 100% in views code.

### Zulip Server 1.5.2

_Released 2017-06-01_

- CVE-2017-0896: Restricting inviting new users to admins was broken.
- CVE-2015-8861: Insecure old version of Handlebars templating engine.

### Zulip Server 1.5.1

_Released 2017-02-07_

- Fix exception trying to copy node_modules during upgrade process.
- Improved styling of /stats page to remove useless login/register links.

### Zulip Server 1.5.0

_Released 2017-02-06_

#### Highlights

- Completely redesigned the Manage streams interface.
- Added support for emoji reactions to messages.
- Added a lightbox for viewing images and videos.
- Added an extensive user documentation site at /help/.
- Added admin setting to auto-linkify certain strings (useful for
  issue numbers and Git commit IDs).
- Upgraded how the main application runs from FastCGI on Django 1.8 to
  uwsgi and Django 1.10.
- Added preliminary support for open graph previews of links (the
  setting, `INLINE_URL_EMBED_PREVIEW`, is disabled by default in this
  release).

#### Full feature changelog

- Added an emoji picker/browser to the compose box.
- Added Markdown preview support to the compose box.
- Added a new analytics system to track interesting usage statistics.
- Added a /stats page with graphs of the analytics data.
- Added display of subscriber counts in Manage streams.
- Added support for filtering streams in Manage streams.
- Added support for setting a stream description on creation.
- Added support for copying subscribers from existing streams on creation.
- Added several new search/filtering UI elements.
- Added UI for deactivating your own Zulip account.
- Added support for viewing the raw Markdown content of a message.
- Added support for deploying Zulip with subdomains for each realm.
  This entailed numerous changes to ensure a consistent experience.
- Added support for (optionally) using PGRoonga to support full-text
  search in all languages (not just English).
- Added AppFollow, GitLab, Google Calendar, GoSquared, HelloSign,
  Heroku, Librato, Mailchimp, Mention, Papertrail, Sentry, Solano
  Labs, Stripe and Zapier integrations.
- Added a webhook integration for GitHub, replacing the deprecated
  github-services hook.
- Normalized the message formatting for all the Zulip Git integrations.
- Added support for VMware Fusion Vagrant provider for faster OSX
  development.
- Added a shields.io style badge for joining a Zulip server.
- Added admin setting for which email domains can join a realm.
- Added admin setting for controlling who can create streams.
- Added admin setting to limit stream creation to older users.
- Added a notification when you muted a topic.
- Added a new hotkey for muting/unmuting topics.
- Added support for testing websockets to the Nagios plugins.
- Added a configuration option to disable websockets.
- Added support for removing one's own Zulip account.
- Added support for realm admins which auth backends are supported.
- Added new organization type concept. This will be used to control
  whether Zulip is optimized around protecting user privacy
  vs. administrative control.
- Added #**streamName** syntax for linking to a stream.
- Added support for viewing Markdown source of messages.
- Added setting to always send push notifications.
- Added setting to hide private message content in desktop
  notifications.
- Added buttons to download .zuliprc files.
- Added italics and strikethrough support in Markdown implementation.
- Added errors for common installations mistakes (e.g. too little RAM).
- Added a new /authors page showing the contributors to the current
  Zulip version.
- Added illustrations to the 404 and 500 pages.
- Upgraded all Python dependencies to modern versions, including
  Django 1.10 (all of Zulip's patches have been merged into mainline).
- Increased backend test coverage of Python codebase to 90%.
- Increased mypy static type coverage of Python code to 100%.
- Added several new linters (eslint, pep8) and cleaned the codebase.
- Optimized the speed of the Zulip upgrade process, especially with Git.
- Have peer_add events send user_id, not email.
- Fixed problems with RabbitMQ when installing Zulip.
- Fixed JavaScript not being gzip-compressed properly.
- Fixed a major performance bug in the Tornado service.
- Fixed a frontend performance bug creating streams in very large realms.
- Fixed numerous bugs where strings were not properly tagged for translation.
- Fixed several real-time sync bugs, and removed several AJAX calls.
  Zulip should be more performant than ever before.
- Fixed Zulip Tornado service not working with http_proxy set in environment.
- Fixed text overflow in stream subscriptions.
- Fixed CSS issues with message topic editing.
- Fixed several transactionality bugs (e.g. in Huddle creation).
- Fixed missed-message email configuration error handling.
- Fixed annoying @-mentions in Jira integration.
- Fixed various mismatches between frontend and backend Markdown
  implementations.
- Fixed various popover-related UI bugs.
- Fixed duplicate notifications with multiple open Zulip tabs.
- Fixed support for emailing the server administrator about backend exceptions.
- Cleaned up the "edit message" form.
- Eliminated most of the legacy API endpoints.
- Improved typeahead and autocomplete across the application.
  Highlights include much better handling of many users with similar names.
- Improved the color scheme for code blocks.
- Improved the message editing UI in several ways.
- Improved how dates are displayed in the UI.
- Improved default settings for zxcvbn password strength checker.
- Upgraded jQuery to the latest 1.12 release.
- Made numerous improvements to the development tooling.
- Made extensive improvements to code organization.
- Restyled all the registration pages to look nicer and be responsive.
- Extensively refactored views to use common functions for fetching
  stream and message objects.
- Suppressed @-all mentions being treated as mentions on muted
  streams.
- Documented preliminary design for interactive bot system.

### Zulip Server 1.4.3

_Released 2017-01-29_

- CVE-2017-0881: Users could subscribe to invite-only streams.

### Zulip Server 1.4.2

_Released 2016-09-27_

- Upgraded Django to version 1.8.15 (with the Zulip patches applied),
  fixing a CSRF vulnerability in Django (see
  https://www.djangoproject.com/weblog/2016/sep/26/security-releases/),
  and a number of other Django bugs from past Django stable releases
  that largely affects parts of Django that are not used by Zulip.
- Fixed buggy logrotate configuration.

### Zulip Server 1.4.1

_Released 2016-09-03_

- Fixed settings bug upgrading from pre-1.4.0 releases to 1.4.0.
- Fixed local file uploads integration being broken for new 1.4.0
  installations.

### Zulip Server 1.4.0

_Released 2016-08-25_

- Migrated Zulip's python dependencies to be installed via a virtualenv,
  instead of the via apt. This is a major change to how Zulip
  is installed that we expect will simplify upgrades in the future.
- Fixed unnecessary loading of zxcvbn password strength checker. This
  saves a huge fraction of the uncached network transfer for loading
  Zulip.
- Added support for using Ubuntu 16.04 in production.
- Added a powerful and complete realm import/export tool.
- Added nice UI for selecting a default language to display settings.
- Added UI for searching streams in left sidebar with hotkeys.
- Added Semaphore, Bitbucket, and HelloWorld (example) integrations.
- Added new webhook-based integration for Trello.
- Added management command for creating realms through web UI.
- Added management command to send password reset emails.
- Added endpoint for mobile apps to query available auth backends.
- Added Let's Encrypt documentation for getting SSL certificates.
- Added nice rendering of Unicode emoji.
- Added support for pinning streams to the top of the left sidebar.
- Added search box for filtering user list when creating a new stream.
- Added realm setting to disable message editing.
- Added realm setting to time-limit message editing. Default is 10m.
- Added realm setting for default language.
- Added year to timestamps in message interstitials for old messages.
- Added GitHub authentication (and integrated python-social-auth, so it's
  easy to add additional social authentication methods).
- Added TERMS_OF_SERVICE setting using Markdown formatting to configure
  the terms of service for a Zulip server.
- Added numerous hooks to Puppet modules to enable more configurations.
- Moved several useful Puppet components into the main Puppet
  manifests (setting a Redis password, etc.).
- Added automatic configuration of PostgreSQL/memcached settings based
  on the server's available RAM.
- Added scripts/upgrade-zulip-from-git for upgrading Zulip from a Git repo.
- Added preliminary support for Python 3. All of Zulip's test suites now
  pass using Python 3.4.
- Added support for `Name <email@example.com>` format when inviting users.
- Added numerous special-purpose settings options.
- Added a hex input field in color picker.
- Documented new Electron beta app and mobile apps in the /apps/ page.
- Enabled Android Google authentication support.
- Enhanced logic for tracking origin of user uploads.
- Improved error messages for various empty narrows.
- Improved missed message emails to better support directly replying.
- Increased backend test coverage of Python code to 85.5%.
- Increased mypy static type coverage of Python code to 95%. Also
  fixed many string annotations to properly handle Unicode.
- Fixed major i18n-related frontend performance regression on
  /#subscriptions page. Saves several seconds of load time with 1k
  streams.
- Fixed Jinja2 migration bug when trying to register an email that
  already has an account.
- Fixed narrowing to a stream from other pages.
- Fixed various frontend strings that weren't marked for translation.
- Fixed several bugs around editing status (/me) messages.
- Fixed queue workers not restarting after changes in development.
- Fixed Casper tests hanging while development server is running.
- Fixed browser autocomplete issue when adding new stream members.
- Fixed broken create_stream and rename_stream management commands.
- Fixed zulip-puppet-apply exit code when puppet throws errors.
- Fixed EPMD restart being attempted on every puppet apply.
- Fixed message cache filling; should improve perf after server restart.
- Fixed caching race condition when changing user objects.
- Fixed buggy Puppet configuration for supervisord restarts.
- Fixed some error handling race conditions when editing messages.
- Fixed fastcgi_params to protect against the httpoxy attack.
- Fixed bug preventing users with mit.edu emails from registering accounts.
- Fixed incorrect settings docs for the email mirror.
- Fixed APNS push notification support (had been broken by Apple changing
  the APNS API).
- Fixed some logic bugs in how attachments are tracked.
- Fixed unnecessarily resource-intensive RabbitMQ cron checks.
- Fixed old deployment directories leaking indefinitely.
- Fixed need to manually add localhost in ALLOWED_HOSTS.
- Fixed display positioning for the color picker on subscriptions page.
- Fixed escaping of Zulip extensions to Markdown.
- Fixed requiring a reload to see newly uploaded avatars.
- Fixed @all warning firing even for `@all`.
- Restyled password reset form to look nice.
- Improved formatting in reset password links.
- Improved alert words UI to match style of other settings.
- Improved error experience when sending to nonexistent users.
- Portions of integrations documentation are now automatically generated.
- Restructured the URLs files to be more readable.
- Upgraded almost all Python dependencies to current versions.
- Substantially expanded and reorganized developer documentation.
- Reorganized production documentation and moved to ReadTheDocs.
- Reorganized .gitignore type files to be written under var/
- Refactored substantial portions of templates to support subdomains.
- Renamed local_settings.py symlink to prod_settings.py for clarity.
- Renamed email-mirror management command to email_mirror.
- Changed HTTP verb for create_user_backend to PUT.
- Eliminated all remaining settings hardcoded for zulip.com.
- Eliminated essentially all remaining hardcoding of mit.edu.
- Optimized the performance of all the test suites.
- Optimized Django memcached configuration.
- Removed old prototype data export tool.
- Disabled insecure RC4 cipher in nginx configuration.
- Enabled shared SSL session cache in nginx configuration.
- Updated header for Zulip static assets to reflect Zulip being
  open source.

### Zulip Server 1.3.13

_Released 2016-06-21_

- Added nearly complete internationalization of the Zulip UI.
- Added warning when using @all/@everyone.
- Added button offering to subscribe at bottom of narrows to streams
  the user is not subscribed to.
- Added integrations with Airbrake, CircleCI, Crashlytics, IFTTT,
  Transifex, and Updown.io.
- Added menu option to mark all messages in a stream or topic as read.
- Added new Attachment model to keep track of uploaded files.
- Added caching of virtualenvs in development.
- Added mypy static type annotations to about 85% of the Zulip Python codebase.
- Added automated test of backend templates to test for regressions.
- Added lots of detailed documentation on the Zulip development environment.
- Added setting allowing only administrators to create new streams.
- Added button to exit the Zulip tutorial early.
- Added web UI for configuring default streams.
- Added new OPEN_REALM_CREATION setting (default off), providing a UI
  for creating additional realms on a Zulip server.
- Fixed email_gateway_password secret not working properly.
- Fixed missing helper scripts for RabbitMQ Nagios plugins.
- Fixed skipping forward to latest messages ("More messages below" button).
- Fixed netcat issue causing Zulip installation to hang on Scaleway machines.
- Fixed rendering of /me status messages after message editing.
- Fixed case sensitivity of right sidebar fading when compose is open.
- Fixed error messages when composing to invalid PM recipients.
- Fixed LDAP auth backend not working with Zulip mobile apps.
- Fixed erroneous WWW-Authenticate headers with expired sessions.
- Changed "coworkers" to "users" in the Zulip UI.
- Changed add_default_stream REST API to correctly use PUT rather than PATCH.
- Updated the Zulip emoji set (the Android emoji) to a modern version.
- Made numerous small improvements to the Zulip development experience.
- Migrated backend templates to the faster Jinja2 templating system.
- Migrated development environment setup scripts to tools/setup/.
- Expanded test coverage for several areas of the product.
- Simplified the API for writing new webhook integrations.
- Removed most of the remaining JavaScript global variables.

### Zulip Server 1.3.12

_Released 2016-05-10_

- CVE-2016-4426: Bot API keys were accessible to other users in the same realm.
- CVE-2016-4427: Deactivated users could access messages if SSO was enabled.
- Fixed a RabbitMQ configuration bug that resulted in reordered messages.
- Added expansive test suite for authentication backends and decorators.
- Added an option to logout_all_users to delete only sessions for deactivated users.

### Zulip Server 1.3.11

_Released 2016-05-02_

- Moved email digest support into the default Zulip production configuration.
- Added options for configuring PostgreSQL, RabbitMQ, Redis, and memcached
  in settings.py.
- Added documentation on using Hubot to integrate with useful services
  not yet integrated with Zulip directly (e.g. Google Hangouts).
- Added new management command to test sending email from Zulip.
- Added Codeship, Pingdom, Taiga, TeamCity, and Yo integrations.
- Added Nagios plugins to the main distribution.
- Added ability for realm administrators to manage custom emoji.
- Added guide to writing new integrations.
- Enabled camo image proxy to fix mixed-content warnings for http images.
- Refactored the Zulip Puppet modules to be more modular.
- Refactored the Tornado event system, fixing old memory leaks.
- Removed many old-style /json API endpoints
- Implemented running queue processors multithreaded in development,
  decreasing RAM requirements for a Zulip development environment from
  ~1GB to ~300MB.
- Fixed rerendering the complete buddy list whenever a user came back from
  idle, which was a significant performance issue in larger realms.
- Fixed the disabling of desktop notifications from 1.3.7 for new users.
- Fixed the (admin) create_user API enforcing restricted_to_domain, even
  if that setting was disabled for the realm.
- Fixed bugs changing certain settings in administration pages.
- Fixed collapsing messages in narrowed views.
- Fixed 500 errors when uploading a non-image file as an avatar.
- Fixed Jira integration incorrectly not @-mentioning assignee.

### Zulip Server 1.3.10

_Released 2016-01-21_

- Added new integration for Travis CI.
- Added settings option to control maximum file upload size.
- Added support for running Zulip development environment in Docker.
- Added easy configuration support for a remote PostgreSQL database.
- Added extensive documentation on scalability, backups, and security.
- Recent private message threads are now displayed expanded similar to
  the pre-existing "Recent topics" feature.
- Made it possible to set LDAP and EMAIL_HOST passwords in
  /etc/zulip/secrets.conf.
- Improved the styling for the Administration page and added tabs.
- Substantially improved loading performance on slow networks by enabling
  gzip compression on more assets.
- Changed the page title in narrowed views to include the current narrow.
- Fixed several backend performance issues affecting very large realms.
- Fixed bugs where draft compose content might be lost when reloading site.
- Fixed support for disabling the "zulip" notifications stream.
- Fixed missing step in postfix_localmail installation instructions.
- Fixed several bugs/inconveniences in the production upgrade process.
- Fixed realm restrictions for servers with a unique, open realm.
- Substantially cleaned up console logging from run-dev.

### Zulip Server 1.3.9

_Released 2015-11-16_

- Fixed buggy #! lines in upgrade scripts.

### Zulip Server 1.3.8

_Released 2015-11-15_

- Added options to the Python API for working with untrusted server certificates.
- Added a lot of documentation on the development environment and testing.
- Added partial support for translating the Zulip UI.
- Migrated installing Node dependencies to use npm.
- Fixed LDAP integration breaking autocomplete of @-mentions.
- Fixed admin panel reactivation/deactivation of bots.
- Fixed inaccurate documentation for downloading the desktop apps.
- Fixed various minor bugs in production installation process.
- Fixed security issue where recent history on private streams might
  be visible to new users (to the Zulip team) who were invited with that
  private stream as one of their initial streams
  (https://github.com/zulip/zulip/issues/230).
- Major preliminary progress towards supporting Python 3.

### Zulip Server 1.3.7

_Released 2015-10-19_

- Turn off desktop and audible notifications for streams by default.
- Added support for the LDAP authentication integration creating new users.
- Added new endpoint to support Google auth on mobile.
- Fixed desktop notifications in modern Firefox.
- Fixed several installation issues for both production and development environments.
- Improved documentation for outgoing SMTP and the email mirror integration.

## Upgrade notes

This section links to the upgrade notes from past releases, so you can
easily read them all when upgrading across multiple releases.

- [Draft upgrade notes for 9.0](#upgrade-notes-for-90)
- [Upgrade notes for 8.0](#upgrade-notes-for-80)
- [Upgrade notes for 7.0](#upgrade-notes-for-70)
- [Upgrade notes for 6.0](#upgrade-notes-for-60)
- [Upgrade notes for 5.0](#upgrade-notes-for-50)
- [Upgrade notes for 4.0](#upgrade-notes-for-40)
- [Upgrade notes for 3.0](#upgrade-notes-for-30)
- [Upgrade notes for 2.1.5](#upgrade-notes-for-215)
- [Upgrade notes for 2.1.0](#upgrade-notes-for-210)
- [Upgrade notes for 2.0.0](#upgrade-notes-for-200)
- [Upgrade notes for 1.9.0](#upgrade-notes-for-190)
- [Upgrade notes for 1.8.0](#upgrade-notes-for-180)
- [Upgrade notes for 1.7.0](#upgrade-notes-for-170)

[docker-zulip]: https://github.com/zulip/docker-zulip
[commit-log]: https://github.com/zulip/zulip/commits/main
[latest-changelog]: https://zulip.readthedocs.io/en/latest/overview/changelog.html
