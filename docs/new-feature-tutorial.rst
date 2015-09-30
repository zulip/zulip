====================
New Feature Tutorial
====================

The changes needed to add a new feature will vary, of course, but this document
provides a general outline of what you may need to do, as well as an example of
the specific steps needed to add a new feature;

General Process
===============

Adding a field to the database
------------------------------

**Update the model:** The server accesses the underlying database in `zerver/
models.py`. Add a new field in the appropriate class.

**Create and run the migration:** The migration process is documented at:
https://docs.djangoproject.com/en/1.8/topics/migrations/

**Test your changes:** Once you've run the migration, restart memcached on your 
development server (``/etc/init.d/memcached restart``) and then restart 
``run-dev.py`` to avoid interacting with cached objects.

Backend changes
---------------

**Database interaction:** Add any necessary code for updating and interacting
with the database in ``zerver/lib/actions.py``. It should update the database and 
send an event announcing the change.

**Application state:** Modify the ``fetch_initial_state_data`` and ``apply_events`` 
functions in ``zerver/lib/actions.py`` to update the state based on the event you 
just created.

**Backend rendering:** Make any other modifications to the backend required for 
your change. This could include the [xxx] file, which controls the generation of 
various pages served (along with the Django templates).

**Testing:** At the very least, add a test of your event data flowing through the system in
``test_events.py``.


Frontend changes
----------------

**JavaScript:** Zulip's JavaScript is located in the directory ``static/js/``. 
The exact files you may need to change depend on your feature. If you've added a 
new event that is sent to clients, be sure to add a handler for it to
``static/js/server_events.js``.

**CSS:** The primary CSS file is ``static/styles/zulip.css``. If your new 
feature requires UI changes, you may need to add additional CSS to this file.

**Templates:** Zulip uses Handlebars templates which are located in
``static/templates``. Templates are precompiled as part of the build/deploy
process.

**Testing:** There are both blackbox, end-to-end front end tests and unit tests. 
The blackbox tests are run in a headless browser using Casper.js and are located
in ``zerver/tests/frontend/tests/``. The unit tests use Node's ``assert`` module
are located in ``zerver/tests/frontend/node/``. For more information on testing
see the :doc:`testing documentation <testing>`.

Example Feature
===============

This example describes the process of adding a new setting to Zulip:
a flag that restricts inviting new users to admins only (the default behavior
is that any user can invite other users).

First, update the database and model to store the new setting. Add a 
new boolean field, ``realm_invite_by_admins_only``, to the Realm model in
``zerver/models.py``.

Then create a Django migration that adds a new field, ``invite_by_admins_only``,
to the ``zerver_realm`` table.

In ``zerver/lib/actions.py``, create a new function named 
``do_set_realm_invite_by_admins_only``. This function will update the database
and trigger an event to notify clients when this setting changes. ::

  # zerver/lib/actions.py

  def do_set_realm_invite_by_admins_only(realm, invite_by_admins_only):
    realm.invite_by_admins_only = invite_by_admins_only
    realm.save(update_fields=['invite_by_admins_only'])
    event = dict(
      type="realm",
      op="update",
      property='invite_by_admins_only',
      value=invite_by_admins_only,
    )
    send_event(event, active_user_ids(realm))
    return {}

You then need to add code that will handle the event and update the application state. In ``zerver/lib/actions.py`` update the ``fetch_initial_state`` and ``apply_events`` functions. ::

  def fetch_initial_state_data(user_profile, event_types, queue_id):
    # ...
    state['realm_invite_by_admins_only'] = user_profile.realm.invite_by_admins_only`

In this case you don't need to change ``apply_events`` because there is already code that will correctly handle this event: ::

  def apply_events(state, events, user_profile):
    for event in events:
      # ...
      elif event['type'] == 'realm':
         field = 'realm_' + event['property']
         state[field] = event['value']

This feature adds a new parameter that should be sent to clients when the
application loads and be accessible via JavaScript, so add it the initial state
in ``zerver/views/__init__.py``. ::

  # zerver/views/__init__.py

  def home(request):
    # ...
    page_params = dict(
      # ...
      realm_invite_by_admins_only = register_ret['realm_invite_by_admins_only'],
      # ...
    )

Since this feature also adds a checkbox to the admin page, and adds a new property the Realm model that can be modified from there, you also need to make changes to the ``update_realm`` function in the same file: ::

  # zerver/views/__init__.py

  def update_realm(request, user_profile,
    name=REQ(validator=check_string, default=None),
    restricted_to_domain=REQ(validator=check_bool, default=None),
    invite_by_admins_only=REQ(validator=check_bool,default=None)):

    # ...

    if invite_by_admins_only is not None and
      realm.invite_by_admins_only != invite_by_admins_only:
        do_set_realm_invite_by_admins_only(realm, invite_by_admins_only)
        data['invite_by_admins_only'] = invite_by_admins_only

Then make the required front end changes: in this case a checkbox needs to be added to the admin page (and its value added to the data sent back to server when a realm is updated) and the change event needs to be handled on the client.

To add the checkbox to the admin page, modify the relevant template, ``static/templates/admin_tab.handlebars`` (omitted here since it is relatively straightforward). Then add code to handle changes to the new form control in ``static/js/admin.js``. ::

  var url = "/json/realm";
  var new_invite_by_admins_only =
    $("#id_realm_invite_by_admins_only").prop("checked");
  data[invite_by_admins_only] = JSON.stringify(new_invite_by_admins_only);

  channel.patch({
    url: url,
    data: data,
    success: function (data) {
      # ...
      if (data.invite_by_admins_only) {
        ui.report_success("New users must be invited by an admin!", invite_by_admins_only_status);
      } else {
        ui.report_success("Any user may now invite new users!", invite_by_admins_only_status);
      }
      # ...
    }
  });

Finally, update ``server_events.js`` to handle related events coming from the server. ::

  # static/js/server_events.js

  function get_events_success(events) {
    # ...
    var dispatch_event = function dispatch_event(event) {
        switch (event.type) {
        # ...
        case 'realm':
          if (event.op === 'update' && event.property === 'invite_by_admins_only') {
            page_params.realm_invite_by_admins_only = event.value;
        }
    }
  }