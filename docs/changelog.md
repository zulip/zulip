# Version History

All notable changes to the Zulip server are documented in this file.

### Unreleased

### 1.4 - 2016-08-25

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
