Using the Development Environment
=================================

This page describes the basic edit/refresh workflows for working with
the Zulip development environment.

## Server

While developing, it's helpful to watch the `run-dev.py` console
output, which will show any errors your Zulip development server
encounters.

If you need to work more closely with authentication systems, or if you need
to use the [Zulip REST API][rest-api], which requires an API key, this [detailed doc][authentication-dev-server]
will help you get started.

Here's what you need to do to see your changes take effect:

* The main Django/Tornado server processes are run on top of Django's
[manage.py runserver][django-runserver], which will automatically
restart them when you save changes to Python code they use.  You can
watch this happen in the `run-dev.py` console to make sure the backend
has reloaded.

* The Python queue workers will also automatically restart when you
save changes.  However, you may need to ctrl-C and then restart
`run-dev.py` manually if a queue worker has crashed.

* If you change the database schema, you'll need to use the standard
Django migrations process to create and then run your migrations; see
the [new feature tutorial][new-feature-tutorial] for an example.
Additionally, you should check out the [detailed testing
docs][testing-docs] for how to run the tests properly after doing a
migration.

(In production, everything runs under supervisord and thus will
restart if it crashes, and `upgrade-zulip` will take care of running
migrations and then cleanly restaring the server for you.)

To manually query the Postgres database, run `psql zulip` for an
interactive console.

## Web

Once the development server is running, you can visit
<http://localhost:9991/> in your browser.  By default, the development
server homepage just shows a list of the users that exist on the
server and you can login as any of them by just clicking on a user.
This setup saves time for the common case where you want to test
something other than the login process. To test the login process,
you'll want to change `AUTHENTICATION_BACKENDS` in the not-PRODUCTION
case of `zproject/settings.py` from zproject.backends.DevAuthBackend
to use the auth method(s) you'd like to test.

Here's what you need to do to see your changes take effect:

* If you change CSS files, your changes will appear immediately via hot module
replacement.
* If you change JavaScript or Handlebars templates, the browser
window will be reloaded automatically.
* For Jinja2 backend templates, you'll need to reload the browser manually
to see changes take effect.

Any JavaScript exceptions encountered while using the webapp in a
development environment will be displayed as a large notice.

## Mobile

See the mobile project's documentation on [using a development server
for mobile development][mobile-dev-server].

[rest-api]: https://zulipchat.com/api/rest
[authentication-dev-server]: ./authentication.md
[django-runserver]: https://docs.djangoproject.com/en/1.8/ref/django-admin/#runserver-port-or-address-port
[new-feature-tutorial]: ../tutorials/new-feature-tutorial.md
[testing-docs]: ../testing/testing.md
[mobile-dev-server]: https://github.com/zulip/zulip-mobile/blob/master/docs/howto/dev-server.md#using-a-dev-version-of-the-server
