====================
New Feature Tutorial
====================

.. attention::
   This tutorial is an unfinished work -- contributions welcome!

The changes needed to add a new feature will vary, of course.  We give an
example here that illustrates some of the common steps needed.  We describe
the process of adding a new setting for admins that restricts inviting new
users to admins only.

Backend Changes
===============

Adding a field to the database
------------------------------

The server accesses the underlying database in `zerver/models.py`.  Add
a new field in the appropriate class, `realm_invite_by_admins_only`
in the `Realm` class in this case.

Once you do so, you need to create the migration and run it; the
process is documented at:
https://docs.djangoproject.com/en/1.8/topics/migrations/

Once you've run the migration, to test your changes, you'll want to
restart memcached on your development server (``/etc/init.d/memcached restart``) and
then restart ``run-dev.py`` to avoid interacting with cached objects.

Backend changes
---------------

You should add code in `zerver/lib/actions.py` to interact with the database,
that actually updates the relevant field.  In this case, `do_set_realm_invite_by_admins_only`
is a function that actually updates the field in the database, and sends
an event announcing that this change has been made.

You then need update the `fetch_initial_state_data` and `apply_events` functions
in `zerver/lib/actions.py` to update the state based on the event you just created.
In this case, we add a line

::

  state['realm_invite_by_admins_only'] = user_profile.realm.invite_by_admins_only`

to the `fetch_initial_state_data` function.  The `apply_events` function
doesn't need to be updated since

::

   elif event['type'] == 'realm':
       field = 'realm_' + event['property']
       state[field] = event['value']

already took care of our event.

Then update `zerver/views/__init__.py` to actually call your function.
In the dictionary which sets the javascript `page_params` dictionary,
add a value for your feature.

::

   realm_invite_by_admins_only = register_ret['realm_invite_by_admins_only']

Perhaps your new option controls some other backend rendering: in our case
we test for this option in the `home` method for adding a variable to the response.
The functions in this file control the generation of various pages served
(along with the Django templates).
Our new feature also shows up in the administration tab (as a checkbox),
so we need to update the `update_realm` function.


Finally, add tests for your backend changes; at the very least you
should add a test of your event data flowing through the system in
``test_events.py``.


Frontend changes
----------------

You need to change various things on the front end.  In this case, the relevant files
are `static/js/server_events.js`, `static/js/admin.js`, `static/styles/zulip.css
and `static/templates/admin_tab.handlebars`.

