# Writing a new application feature

The changes needed to add a new feature will vary, of course, but this
document provides a general outline of what you may need to do, as well
as an example of the specific steps needed to add a new feature: adding
a new option to the application that is dynamically synced through the
data system in real-time to all browsers the user may have open.

## General Process in brief

### Adding a field to the database

**Update the model:** The server accesses the underlying database in
`zerver/ models.py`. Add a new field in the appropriate class.

**Create and run the migration:** To create and apply a migration, run:

```
./manage.py makemigrations
./manage.py migrate
```

**Test your changes:** Once you've run the migration, restart memcached
on your development server (`/etc/init.d/memcached restart`) and then
restart `run-dev.py` to avoid interacting with cached objects.

### Backend changes

**Database interaction:** Add any necessary code for updating and
interacting with the database in `zerver/lib/actions.py`. It should
update the database and send an event announcing the change.

**Application state:** Modify the `fetch_initial_state_data` and
`apply_events` functions in `zerver/lib/actions.py` to update the state
based on the event you just created.

**Backend implementation:** Make any other modifications to the backend
required for your change.

**New views:** Add any new application views to `zerver/urls.py`. This
includes both views that serve HTML (new pages on Zulip) as well as new
API endpoints that serve JSON-formatted data.

**Testing:** At the very least, add a test of your event data flowing
through the system in `test_events.py`.

### Frontend changes

**JavaScript:** Zulip's JavaScript is located in the directory
`static/js/`. The exact files you may need to change depend on your
feature. If you've added a new event that is sent to clients, be sure to
add a handler for it to `static/js/server_events.js`.

**CSS:** The primary CSS file is `static/styles/zulip.css`. If your new
feature requires UI changes, you may need to add additional CSS to this
file.

**Templates:** The initial page structure is rendered via Jinja2
templates located in `templates/zerver`. For JavaScript, Zulip uses
Handlebars templates located in `static/templates`. Templates are
precompiled as part of the build/deploy process.

**Testing:** There are two types of frontend tests: node-based unit
tests and blackbox end-to-end tests. The blackbox tests are run in a
headless browser using Casper.js and are located in
`frontend_tests/casper_tests/`. The unit tests use Node's `assert`
module are located in `frontend_tests/node_tests/`. For more
information on writing and running tests see the [testing
documentation](testing.html).

## Example Feature

This example describes the process of adding a new setting to Zulip: a
flag that restricts inviting new users to admins only (the default
behavior is that any user can invite other users). It is based on an
actual Zulip feature, and you can review [the original commit in the
Zulip git
repo](https://github.com/zulip/zulip/commit/5b7f3466baee565b8e5099bcbd3e1ccdbdb0a408).
(Note that Zulip has since been upgraded from Django 1.6 to 1.8, so the
migration format has changed.)

### Update the model

First, update the database and model to store the new setting. Add a new
boolean field, `invite_by_admins_only`, to the Realm model in
`zerver/models.py`.

``` diff
--- a/zerver/models.py
+++ b/zerver/models.py
@@ -139,6 +139,7 @@ class Realm(ModelReprMixin, models.Model):
     restricted_to_domain = models.BooleanField(default=True) # type: bool
     invite_required = models.BooleanField(default=False) # type: bool
+    invite_by_admins_only = models.BooleanField(default=False) # type: bool
     create_stream_by_admins_only = models.BooleanField(default=False) # type: bool
     mandatory_topics = models.BooleanField(default=False) # type: bool
```

### Create the migration

Create the migration file: `./manage.py makemigrations`. Make sure to
commit the generated file to git: `git add zerver/migrations/NNNN_realm_invite_by_admins_only.py`
(NNNN is a number that is equal to the number of migrations.)

If you run into problems, the [Django migration documentation](https://docs.djangoproject.com/en/1.8/topics/migrations/) is helpful.

### Test your migration changes

Apply the migration: `./manage.py migrate`

Output:
```
shell $ ./manage.py migrate
Operations to perform:
  Synchronize unmigrated apps: staticfiles, analytics, pipeline
  Apply all migrations: zilencer, confirmation, sessions, guardian, zerver, sites, auth, contenttypes
Synchronizing apps without migrations:
  Creating tables...
    Running deferred SQL...
  Installing custom SQL...
Running migrations:
  Rendering model states... DONE
  Applying zerver.0026_realm_invite_by_admins_only... OK
```

### Handle database interactions

Next, we will move on to implementing the backend part of this feature.
Like typical apps, we will need our backend to update the database and
send some response to the client that made the request.

Beyond that, we need to orchestrate notifications to *other*
clients (or other users, if you will) that our setting has changed.
Clients find out about settings through two closely related code
paths.  When a client first contacts the server, the server sends
the client its initial state.  Subsequently, clients subscribe to
"events," which can (among other things) indicate that settings have
changed.  For the backend piece, we will need our action to make a call to
`send_event` to send the event to clients that are active.  We will
also need to modify `fetch_initial_state_data` so that future clients
see the new changes.

Anyway, getting back to implementation details...

In `zerver/lib/actions.py`, create a new function named
`do_set_realm_invite_by_admins_only`. This function will update the
database and trigger an event to notify clients when this setting
changes. In this case there was an existing `realm|update` event type
which was used for setting similar flags on the Realm model, so it was
possible to add a new property to that event rather than creating a new
one. The property name matches the database field to make it easy to
understand what it indicates.

The second argument to `send_event` is the list of users whose browser
sessions should be notified. Depending on the setting, this can be a
single user (if the setting is a personal one, like time display
format), only members in a particular stream or all active users in a
realm. :

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

### Update application state

You then need to add code that will handle the event and update the
application state. In `zerver/lib/actions.py` update the
`fetch_initial_state` and `apply_events` functions. :

    def fetch_initial_state_data(user_profile, event_types, queue_id):
      # ...
      state['realm_invite_by_admins_only'] = user_profile.realm.invite_by_admins_only`

In this case you don't need to change `apply_events` because there is
already code that will correctly handle the realm update event type: :

    def apply_events(state, events, user_profile):
      for event in events:
        # ...
        elif event['type'] == 'realm':
           field = 'realm_' + event['property']
           state[field] = event['value']

### Add a new view

You then need to add a view for clients to access that will call the
newly-added `actions.py` code to update the database. This example
feature adds a new parameter that should be sent to clients when the
application loads and be accessible via JavaScript, and there is already
a view that does this for related flags: `update_realm`. So in this
case, we can add out code to the existing view instead of creating a
new one. :

    # zerver/views/__init__.py

    def home(request):
      # ...
      page_params = dict(
        # ...
        realm_invite_by_admins_only = register_ret['realm_invite_by_admins_only'],
        # ...
      )

Since this feature also adds a checkbox to the admin page, and adds a
new property the Realm model that can be modified from there, you also
need to make changes to the `update_realm` function in the same file: :

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

Then make the required front end changes: in this case a checkbox needs
to be added to the admin page (and its value added to the data sent back
to server when a realm is updated) and the change event needs to be
handled on the client.

To add the checkbox to the admin page, modify the relevant template,
`static/templates/admin_tab.handlebars` (omitted here since it is
relatively straightforward). Then add code to handle changes to the new
form control in `static/js/admin.js`. :

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

Finally, update `server_events.js` to handle related events coming from
the server. :

    # static/js/server_events.js

    function dispatch_normal_event(event) {
        switch (event.type) {
        # ...
        case 'realm':
            if (event.op === 'update' && event.property === 'invite_by_admins_only') {
                page_params.realm_invite_by_admins_only = event.value;
            }
        }
    }

Any code needed to update the UI should be placed in
`dispatch_normal_event` callback (rather than the `channel.patch`)
function. This ensures the appropriate code will run even if the
changes are made in another browser window. In this example most of
the changes are on the backend, so no UI updates are required.
