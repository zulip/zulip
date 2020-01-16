Using the Development Environment
=================================

This page describes the basic edit/refresh workflows for working with
the Zulip development environment.  Generally, the development
environment will automatically update as soon as you save changes
using your editor.  Details for work on the [server](#server),
[webapp](#web), and [mobile apps](#mobile) are below.

If you're working on authentication methods or need to use the [Zulip
REST API][rest-api], which requires an API key, see [authentication in
the development environment][authentication-dev-server].

## Common (linting and testing)

* After making changes, you'll often want to run the
  [linters](../testing/linters.md) and relevant [test
  suites](../testing/testing.md).  All of our test suites are designed
  to support quickly testing just a single file or test case, which
  you should take advantage of to save time.  Consider using our [Git
  pre-commit hook](../git/zulip-tools.html#set-up-git-repo-script) to
  automatically lint changes when you commit them.

## Server

* For changes that don't affect the database model, the Zulip
  development environment will automatically detect changes and
  restart:
    * The main Django/Tornado server processes are run on top of
    Django's [manage.py runserver][django-runserver], which will
    automatically restart them when you save changes to Python code
    they use.  You can watch this happen in the `run-dev.py` console
    to make sure the backend has reloaded.
   * The Python queue workers will also automatically restart when you
   save changes.  However, you may need to ctrl-C and then restart
   `run-dev.py` manually if a queue worker has crashed.
* If you change the database schema (`zerver/models.py`), you'll need
  to use the [Django migrations
  process](../subsystems/schema-migrations.md) to create and then run
  your migrations; see the [new feature
  tutorial][new-feature-tutorial] for an example.
* While testing server changes, it's helpful to watch the `run-dev.py`
  console output, which will show tracebacks for any 500 errors your
  Zulip development server encounters.
* To manually query the Postgres database interactively, use
  `./manage.py shell` or `manage.py dbshell` depending whether you
  prefer an iPython shell or SQL shell.
* The database(s) used for the automated tests are independent from
  the one you use for manual testing in the UI, so changes you make to
  the database manually will never affect the automated tests.

## Web

* Once the development server (`run-dev.py`) is running, you can visit
  <http://localhost:9991/> in your browser.
* By default, the development server homepage just shows a list of the
  users that exist on the server and you can login as any of them by
  just clicking on a user.
    * This setup saves time for the common case where you want to test
    something other than the login process.
    * You can test the login or registration process by clicking the
    links for the normal login page.
* If you change CSS files, your changes will appear immediately via
  webpack hot module replacement.
* If you change JavaScript code (`static/js`) or Handlebars templates
  (`static/templates`), the browser window will be reloaded
  automatically.
* For Jinja2 backend templates (`templates/*`), you'll need to reload
  the browser manually to see changes take effect.
* Any JavaScript exceptions encountered while using the webapp in a
  development environment will be displayed as a large notice, so you
  don't need to watch the JavaScript console for exceptions.

## Mobile

See the mobile project's documentation on [using a development server
for mobile development][mobile-dev-server].

[rest-api]: https://zulipchat.com/api/rest
[authentication-dev-server]: ./authentication.md
[django-runserver]: https://docs.djangoproject.com/en/1.8/ref/django-admin/#runserver-port-or-address-port
[new-feature-tutorial]: ../tutorials/new-feature-tutorial.md
[testing-docs]: ../testing/testing.md
[mobile-dev-server]: https://github.com/zulip/zulip-mobile/blob/master/docs/howto/dev-server.md#using-a-dev-version-of-the-server
