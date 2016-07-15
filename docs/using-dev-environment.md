Using the Development Environment
=================================

Once the development environment is running, you can visit
<http://localhost:9991/> in your browser.  By default, the development
server homepage just shows a list of the users that exist on the
server and you can login as any of them by just clicking on a user.
This setup saves time for the common case where you want to test
something other than the login process; to test the login process
you'll want to change `AUTHENTICATION_BACKENDS` in the not-PRODUCTION
case of `zproject/settings.py` from zproject.backends.DevAuthBackend
to use the auth method(s) you'd like to test.

While developing, it's helpful to watch the `run-dev.py` console
output, which will show any errors your Zulip development server
encounters.

When you make a change, here's a guide for what you need to do in
order to see your change take effect in Development:

* If you change JavaScript, CSS, or Jinja2 backend templates (under
`templates/`), you'll just need to reload the browser window to see
changes take effect.  The Handlebars frontend HTML templates
(`static/templates`) are automatically recompiled by the
`tools/compile-handlebars-templates` job, which runs as part of
`tools/run-dev.py`.

* If you change Python code used by the the main Django/Tornado server
processes, these services are run on top of Django's [manage.py
runserver][django-runserver] which will automatically restart the
Zulip Django and Tornado servers whenever you save changes to Python
code.  You can watch this happen in the `run-dev.py` console to make
sure the backend has reloaded.

* The Python queue workers will also automatically restart when you
save changes.  However, you may need to ctrl-C and then restart
`run-dev.py` manually if a queue worker has crashed.

* If you change the database schema, you'll need to use the standard
Django migrations process to create and then run your migrations; see
the [new feature tutorial][new-feature-tutorial] for an example.
Additionally you should check out the [detailed testing
docs][testing-docs] for how to run the tests properly after doing a
migration.

(In production, everything runs under supervisord and thus will
restart if it crashes, and `upgrade-zulip` will take care of running
migrations and then cleanly restaring the server for you).

[django-runserver]: https://docs.djangoproject.com/en/1.8/ref/django-admin/#runserver-port-or-address-port
[new-feature-tutorial]: http://zulip.readthedocs.io/en/latest/new-feature-tutorial.html
[testing-docs]: http://zulip.readthedocs.io/en/latest/testing.html
