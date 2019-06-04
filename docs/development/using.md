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

To manually query the Postgres database, run `psql zulip` for an
interactive console.

When you make a change, here's a guide for what you need to do in
order to see your change take effect in Development:

* If you change CSS files, your changes will appear immediately via hot module
replacement. If you change JavaScript or Handlebars templates, the browser
window will be reloaded automatically. For Jinja2 backend templates, you'll
need to reload the browser manually to see changes take effect.

* If you change Python code used by the main Django/Tornado server
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

## Accessing the Vagrant development environment from other systems

If you want to access your Vagrant development environment from outside of it,
then you'll need to follow a few extra steps.

This is required when dealing with testing third-party services like Jira and
Bitbucket Server which can be hosted locally if you want to allow these
services to be able to directly post to your Zulip development enviroment.
Or if you're testing the mobile app and need to use a locally hosted
development version of the zulip server.

To do either one of these you'll need to make sure that your Zulip development
environment (notably the Vagrant virtual machine) is accessible externally.

1. Get the Vagrant VM to listen on all available addresses.
Open zulip/Vagrantfile. Replace the line `host_ip_addr = "127.0.0.1"` with
`host_ip_addr = "0.0.0.0"`. This means that the VM is now listening on all IPv4
addresses available on your local machine. This will allow other services like
Jira or Bitbucket Server to now communicate with Zulip running on the
development server.

2. Figure out your IP address.
If you're using Linux, this can be found by running `ifconfig`, or
`ipconfig /all` if you're on Windows, outside of the Zulip development
environment (on your local PC). In the output you should see a line resembling
`inet 192.168.1.7`, in this case `192.168.1.7` would be your IP address.

3. Set EXTERNAL_HOST.
Like most complex web apps, the Zulip server has an idea internally of what
base URL it's supposed to be accessed at; we call this setting `EXTERNAL_HOST`.
In development, the setting is normally `localhost:9991`, and corresponds to a
base URL of `http://localhost:9991/`.

Set this to `IPADDRESS:9991`, where `IPADDRESS` is the address you identified
in the previous step. In development, we can do this with an environment
variable. For example, if your IP address is `192.168.1.7` then the environment
variable can be set using the command: `export EXTERNAL_HOST="192.168.1.7:9991"`

4. Running the development environment.
Now, from the vagrant development environment, run the server by doing
`./tools/run-dev.py --interface=''`.


[django-runserver]: https://docs.djangoproject.com/en/1.8/ref/django-admin/#runserver-port-or-address-port
[new-feature-tutorial]: ../tutorials/new-feature-tutorial.md
[testing-docs]: ../testing/testing.md
