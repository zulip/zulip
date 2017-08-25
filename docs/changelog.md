# Version History

All notable changes to the Zulip server are documented in this file.

### Unreleased

This section lists notable unreleased changes; it is generally updated
bursts.

Highlights:

- Added a new "incoming webhook" bot type, limited to only sending
  messages into Zulip, for better security.
- Dramatically improved the search typeahead experience when using
  multiple operators.
- Overhauled the emails sent by Zulip to be more consistent and
  readable.
- Added support for iOS mobile push notifications.
- Completely redesigned the /integrations and /apps pages to be
  more usable and more attractive.
- Redesigned several settings subpages to be visually cleaner.
- Redesigned the /help/ documentation site to have a nice sidebar
  index.
- Added support for outgoing webhooks.
- We're now recommending the new electron desktop app to everyone.
  Users should upgrade to the new desktop app; the legacy desktop app
  from 2014 doesn't support useful browser features like local
  storage and will be deprecated completely soon.
- Added a new API for fetching unread messages organized by topic to
  support the mobile apps.  The React Native app will likely start
  requiring Zulip 1.7 soon.  We don't intend to break app
  compatibility with older server versions often, but it makes sense
  in this case, since the new API is critical for providing a great
  mobile experience.

Release notes:

* There are some significant database migrations that will be in the
next release that can take several minutes to run.  These migrations
will be automatically run during the upgrade process, but before
user-facing downtime begins to avoid disruption.  However, if you'd
like to watch the downtime part of the upgrade process carefully, we
recommend
[running these migrations manually](expensive-migrations.html) before
starting the upgrade.

* We fixed Zulip's previously buggy support for multiple organizations
on the same Zulip server.  A consequence of doing this correctly means
is that we require each organization to have its own subdomain.  This
change should have no effect for the vast major of Zulip servers that
only have one organization.  If you manage a server that hosts
multiple organizations, you'll want to read
[our guide on multiple organizations](prod-multiple-organizations.html).

Full feature Changelog:

- Simplified the process for installing a new Zulip server.
- Added support for changing the notifications stream.
- Added development tools to make iterating on emails and error pages
easy.
- Added 'u' hotkey to show a user's profile.
- Added '-' hotkey to toggle collapsing a message.
- Added an organization setting to require topics in stream messages.
- Added an organization setting to control whether edit history is available.
- Added a confirmation dialogue when inviting many users to a new stream.
- Improved design for /stats page and added a link to it in the gear menu.
- Improved how timestamps are displayed across the product.
- Improved the appearance of mention/compose typeahead.
- Significantly improved sort ordering for the emoji picker.
- Fixed most accessibility errors detected by major accessibility
  checker tools.
- Extracted Zulip's Python API and bots ecosystem into its own
  repository, zulip/python-zulip-api.
- Enter hotkey now opens compose in empty narrows.
- Significantly improved performance of "starred messages" and
  "mentions" database queries through new indexes.
- Upgraded to Django 1.11.x.
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
- Fixed rendering of realm emoji in missed-message emails.
- Zulip now will gracefully handle the Postgres server being restarted.
- Simplified the settings for configuring senders for our emails.
- Emoji can now be typed with spaces, e.g. entering "robot face" in
  the typeahead as well as "robot_face".
- Improved title and alt text for unicode emoji.
- Removed the obsolete shortname-based syntax
- Removed the old django-guardian dependency.
- Partially completed migration to webpack as our static asset bundler.

### 1.6.0 -- 2017-06-06

Highlights:

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

[mobile-push]: https://zulip.readthedocs.io/en/latest/prod-mobile-push-notifications.html
[electron-app]: https://github.com/zulip/zulip-electron/releases
[ios-app]: https://itunes.apple.com/us/app/zulip/id1203036395

Full feature Changelog:

* Added Basecamp, Gogs, Greenhouse, Home Assistant, Slack, Splunk, and
  WordPress webhook integrations.
* Added LaTeX support to the markdown processor.
* Added support for filtering branches to all Git integrations.
* Added read-only access to organization-level settings for all users.
* Added UI for managing muted topics and uploaded files.
* Added UI for displaying message edit history.
* Added support for various features needed by new mobile app.
* Added deep links for settings/subscriptions interfaces.
* Added an animation when messages are edited.
* Added support for registration with GitHub auth (not just login).
* Added tracking of uploaded file quotas.
* Added option to display emoji as their alt codes.
* Added new audit log table, to eventually support an auditing UI.
* Added several new permissions-related organization settings.
* Added new endpoint for fetching presence data, useful in employee directories.
* Added typeahead for language for syntax highlighting in code blocks.
* Added support for basic markdown in stream descriptions.
* Added email notifications on new Zulip logins.
* Added security hardening before serving uploaded files.
* Added new PRIVACY_POLICY setting to provide a Markdown privacy policy.
* Added an icon to distinguish bot users as message senders.
* Added a command-line Slack importer tool using the API.
* Added new announcement notifications on stream creation.
* Added support for some newer unicode emoji code points.
* Added support for users deleting realm emoji they themselves uploaded.
* Added support for organization administrators deleting messages.
* Extended data available to mobile apps to cover the entire API.
* Redesigned bots UI.  Now can change owners and reactivate bots.
* Redesigned the visuals of code blocks to be prettier.
* Changed right sidebar presence UI to only show recently active users
  in large organizations.  This has a huge performance benefit.
* Changed color for private messages to look better.
* Converted realm emoji to be uploaded, not links, for better robustness.
* Switched the default password hasher for new passwords to Argon2.
* Increased the paragraph spacing, making multi-paragraph.
* Improved formatting of all Git integrations.
* Improved the UI of the /stats analytics pages.
* Improved search typeahead to support group private messages.
* Improved logic for when the compose box should open/close.
* Improved lightbox to support scrolling through images.
* Improved markdown support for bulleted lists.
* Improved copy-to-clipboard support in various places.
* Improved subject lines of missed message emails.
* Improved handling of users trying to login with Oauth without an account.
* Improved UI of off-the-Internet errors to not be hidden in narrow windows.
* Improved rate-limiting errors to be more easily machine-readable.
* Parallelized the backend test suite; now runs 1600 tests in <30s.
* Fixed numerous bugs and performance issues with stream management.
* Fixed an issue with the fake emails assigned to bot users.
* Fixed a major performance issue in stream creation.
* Fixed numerous minor accessibility issues.
* Fixed a subtle interaction between click-to-reply and copy-paste.
* Fixed various formatting issues with /me messages.
* Fixed numerous real-time sync issues involving users changing their
  name, avatar, or email address and streams being renamed.
* Fixed numerous performance issues across the project.
* Fixed various left sidebar ordering and live-updated bugs.
* Fixed numerous bugs with the message editing widget.
* Fixed missing logging / rate limiting on browser endpoints.
* Fixed regressions in Zulip's browser state preservation on reload logic.
* Fixed support for unicode characters in the email mirror system.
* Fixed load spikes when email mirror is receiving a lot of traffic.
* Fixed the ugly grey flicker when scrolling fast on Macs.
* Fixed previews of GitHub image URLs.
* Fixed narrowing via clicking on desktop notifications.
* Fixed Subscribed/Unsubscribed bookends appearing incorrectly.
* Eliminated the idea of a realm having a canonical domain; now
  there's simply the list of allowed domains for new users.
* Migrated avatars to a user-id-based storage setup (not email-based).
* Trailing whitespace is now stripped in code blocks, avoiding
  unnecessary scrollbars.
* Most API payloads now refer to users primarily by user ID, with
  email available for backwards-compatibility.  In the future, we may
  remove email support.
* Cleaned up Zulip's supervisord configuration.  A side effect is the
  names of the log files have changed for all the queue workers.
* Refactored various endpoints to use a single code path for security
  hardening.
* Removed support for the `MANDRILL_CLIENT` setting.  It hadn't been
  used in years.
* Changed `NOREPLY_EMAIL_ADDRESS` setting to `Name <user@example.com>`
  format.
* Disabled the web tutorial on mobile.
* Backend test coverage is now 93%, with 100% in views code.

### 1.5.2 -- 2017-06-01

- CVE-2017-0896: Restricting inviting new users to admins was broken.
- CVE-2015-8861: Insecure old version of handlebars templating engine.

### 1.5.1 -- 2017-02-07

- Fix exception trying to copy node_modules during upgrade process.
- Improved styling of /stats page to remove useless login/register links.

### 1.5.0 -- 2017-02-06

Highlights:

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

Full feature Changelog:

- Added an emoji picker/browser to the compose box.
- Added markdown preview support to the compose box.
- Added a new analytics system to track interesting usage statistics.
- Added a /stats page with graphs of the analytics data.
- Added display of subscriber counts in Manage streams.
- Added support for filtering streams in Manage streams.
- Added support for setting a stream description on creation.
- Added support for copying subscribers from existing streams on creation.
- Added several new search/filtering UI elements.
- Added UI for deactivating your own Zulip account.
- Added support for viewing the raw markdown content of a message.
- Added support for deploying Zulip with subdomains for each realm.
  This entailed numerous changes to ensure a consistent experience.
- Added support for (optionally) using PGRoonga to support full-text
  search in all languages (not just English).
- Added AppFollow, GitLab, Google Calendar, GoSquared, HelloSign,
  Heroku, Librato, MailChimp, Mention, Papertrail, Sentry, Solano
  Labs, Stripe and Zapier integrations.
- Added a webhook integration for GitHub, replacing the deprecated
  github-services hook.
- Normalized the message formatting for all the Zulip Git integrations.
- Added support for VMWare Fusion Vagrant provider for faster OSX
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
- Added new organization type concept.  This will be used to control
  whether Zulip is optimized around protecting user privacy
  vs. administrative control.
- Added #**streamName** syntax for linking to a stream.
- Added support for viewing markdown source of messages.
- Added setting to always send push notifications.
- Added setting to hide private message content in desktop
  notifications.
- Added buttons to download .zuliprc files.
- Added italics and strikethrough support in markdown implementation.
- Added errors for common installations mistakes (e.g. too little RAM).
- Added a new /authors page showing the contributors to the current
  Zulip version.
- Upgraded all Python dependencies to modern versions, including
  Django 1.10 (all of Zulip's patches have been merged into mainline).
- Increased backend test coverage of Python codebase to 90%.
- Increased mypy static type coverage of Python code to 100%.
- Added several new linters (eslint, pep8) and cleaned the codebase.
- Optimized the speed of the Zulip upgrade process, especially with Git.
- Have peer_add events send user_id, not email.
- Fixed problems with rabbitmq when installing Zulip.
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
- Fixed various mismatches between frontend and backend markdown
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

### 1.4.3 - 2017-01-29
- CVE-2017-0881: Users could subscribe to invite-only streams.

### 1.4.2 - 2016-09-27

- Upgraded Django to version 1.8.15 (with the Zulip patches applied),
  fixing a CSRF vulnerability in Django (see
  https://www.djangoproject.com/weblog/2016/sep/26/security-releases/),
  and a number of other Django bugs from past Django stable releases
  that largely affects parts of Django that are not used by Zulip.
- Fixed buggy logrotate configuration.

### 1.4.1 - 2016-09-03

- Fixed settings bug upgrading from pre-1.4.0 releases to 1.4.0.
- Fixed local file uploads integration being broken for new 1.4.0
  installations.

### 1.4.0 - 2016-08-25

- Migrated Zulip's python dependencies to be installed via a virtualenv,
  instead of the via apt.  This is a major change to how Zulip
  is installed that we expect will simplify upgrades in the future.
- Fixed unnecessary loading of zxcvbn password strength checker.  This
  saves a huge fraction of the uncached network transfer for loading
  Zulip.
- Added support for using Ubuntu Xenial in production.
- Added a powerful and complete realm import/export tool.
- Added nice UI for selecting a default language to display settings.
- Added UI for searching streams in left sidebar with hotkeys.
- Added Semaphore, Bitbucket, and HelloWorld (example) integrations.
- Added new webhook-based integration for Trello.
- Added management command for creating realms through web UI.
- Added management command to send password reset emails.
- Added endpoint for mobile apps to query available auth backends.
- Added LetsEncrypt documentation for getting SSL certificates.
- Added nice rendering of unicode emoji.
- Added support for pinning streams to the top of the left sidebar.
- Added search box for filtering user list when creating a new stream.
- Added realm setting to disable message editing.
- Added realm setting to time-limit message editing.  Default is 10m.
- Added realm setting for default language.
- Added year to timestamps in message interstitials for old messages.
- Added GitHub authentication (and integrated python-social-auth, so it's
  easy to add additional social authentication methods).
- Added TERMS_OF_SERVICE setting using markdown formatting to configure
  the terms of service for a Zulip server.
- Added numerous hooks to puppet modules to enable more configurations.
- Moved several useful puppet components into the main puppet
  manifests (setting a redis password, etc.).
- Added automatic configuration of postgres/memcached settings based
  on the server's available RAM.
- Added scripts/upgrade-zulip-from-git for upgrading Zulip from a Git repo.
- Added preliminary support for Python 3.  All of Zulip's test suites now
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
- Increased mypy static type coverage of Python code to 95%.  Also
  fixed many string annotations to properly handle unicode.
- Fixed major i18n-related frontend performance regression on
  /#subscriptions page.  Saves several seconds of load time with 1k
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
- Fixed buggy puppet configuration for supervisord restarts.
- Fixed some error handling race conditions when editing messages.
- Fixed fastcgi_params to protect against the httpoxy attack.
- Fixed bug preventing users with mit.edu emails from registering accounts.
- Fixed incorrect settings docs for the email mirror.
- Fixed APNS push notification support (had been broken by Apple changing
  the APNS API).
- Fixed some logic bugs in how attachments are tracked.
- Fixed unnecessarily resource-intensive rabbitmq cron checks.
- Fixed old deployment directories leaking indefinitely.
- Fixed need to manually add localhost in ALLOWED_HOSTS.
- Fixed display positioning for the color picker on subscriptions page.
- Fixed escaping of Zulip extensions to markdown.
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

### 1.3.13 - 2016-06-21
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
- Updated the Zulip emoji set (the Android Emoji) to a modern version.
- Made numerous small improvements to the Zulip development experience.
- Migrated backend templates to the faster Jinja2 templating system.
- Migrated development environment setup scripts to tools/setup/.
- Expanded test coverage for several areas of the product.
- Simplified the API for writing new webhook integrations.
- Removed most of the remaining JavaScript global variables.

### 1.3.12 - 2016-05-10
- CVE-2016-4426: Bot API keys were accessible to other users in the same realm.
- CVE-2016-4427: Deactivated users could access messages if SSO was enabled.
- Fixed a RabbitMQ configuration bug that resulted in reordered messages.
- Added expansive test suite for authentication backends and decorators.
- Added an option to logout_all_users to delete only sessions for deactivated users.

### 1.3.11 - 2016-05-02
- Moved email digest support into the default Zulip production configuration.
- Added options for configuring Postgres, RabbitMQ, Redis, and memcached
  in settings.py.
- Added documentation on using Hubot to integrate with useful services
  not yet integrated with Zulip directly (e.g. Google Hangouts).
- Added new management command to test sending email from Zulip.
- Added Codeship, Pingdom, Taiga, Teamcity, and Yo integrations.
- Added Nagios plugins to the main distribution.
- Added ability for realm administrators to manage custom emoji.
- Added guide to writing new integrations.
- Enabled camo image proxy to fix mixed-content warnings for http images.
- Refactored the Zulip puppet modules to be more modular.
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

### 1.3.10 - 2016-01-21
- Added new integration for Travis CI.
- Added settings option to control maximum file upload size.
- Added support for running Zulip development environment in Docker.
- Added easy configuration support for a remote postgres database.
- Added extensive documentation on scalability, backups, and security.
- Recent private message threads are now displayed expanded similar to
  the pre-existing recent topics feature.
- Made it possible to set LDAP and EMAIL_HOST passwords in
  /etc/zulip/secrets.conf.
- Improved the styling for the Administration page and added tabs.
- Substantially improved loading performance on slow networks by enabling
  GZIP compression on more assets.
- Changed the page title in narrowed views to include the current narrow.
- Fixed several backend performance issues affecting very large realms.
- Fixed bugs where draft compose content might be lost when reloading site.
- Fixed support for disabling the "zulip" notifications stream.
- Fixed missing step in postfix_localmail installation instructions.
- Fixed several bugs/inconveniences in the production upgrade process.
- Fixed realm restrictions for servers with a unique, open realm.
- Substantially cleaned up console logging from run-dev.py.

### 1.3.9 - 2015-11-16
- Fixed buggy #! lines in upgrade scripts.

### 1.3.8 - 2015-11-15
- Added options to the Python api for working with untrusted server certificates.
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

### 1.3.7 - 2015-10-19
- Turn off desktop and audible notifications for streams by default.
- Added support for the LDAP authentication integration creating new users.
- Added new endpoint to support Google auth on mobile.
- Fixed desktop notifications in modern Firefox.
- Fixed several installation issues for both production and development environments.
- Improved documentation for outgoing SMTP and the email mirror integration.
