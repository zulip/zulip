# Writing a new application feature

The changes needed to add a new feature will vary, of course, but this
document provides a general outline of what you may need to do, as well
as an example of the specific steps needed to add a new feature: adding
a new option to the application that is dynamically synced through the
data system in real-time to all browsers the user may have open.

As you read this, you may find you need to learn about Zulip's
real-time push system; the
[real-time push and events](events-system.html) documentation has a
detailed explanation of how everything works.

## General Process

### Files impacted

This tutorial will walk through adding a new feature to a Realm (an
organization in Zulip). The following files are involved in the process:

**Backend**
- `zerver/model.py`: Defines the database model.
- `zerver/views/realm.py`: The view function that implements the API endpoint
  for editing realm objects.
- `zerver/lib/actions.py`: Contains code for updating and interacting with the database.
- `zerver/lib/events.py`: Ensures that the state Zulip sends to clients is always
  consistent and correct.

**Frontend**
- `static/templates/settings/organization-permissions-admin.handlebars`: defines
   the structure of the admin permissions page (checkboxes for each organization
   permission setting).
- `static/js/settings_org.js`: handles organization setting form submission.
- `static/js/server_events_dispatch.js`: handles events coming from the server
  (ex: pushing an organization change to other open browsers and updating
  the application's state).

**Backend Testing**
- `zerver/tests/test_realm.py`: end-to-end API tests for updating realm settings.
- `zerver/tests/test_events.py`: tests for possible race bugs in the
  zerver/lib/events.py implementation.

**Frontend Testing**
- `frontend_tests/casper_tests/10-admin.js`: end-to-end tests for the organization
  admin settings pages.
- `frontend_tests/node_tests/dispatch.js`

### Adding a field to the database

**Update the model:** The server accesses the underlying database in
`zerver/models.py`. Add a new field in the appropriate class.

**Create and run the migration:** To create and apply a migration, run:

```
./manage.py makemigrations
./manage.py migrate
```

**Test your changes:** Once you've run the migration, flush memcached
on your development server (`./scripts/setup/flush-memcached`) and then
[restart the development server](
http://zulip.readthedocs.io/en/latest/dev-remote.html?highlight=tools%2Frun-dev.py#running-the-development-server)
to avoid interacting with cached objects.

### Backend changes

We have a framework that automatically handles many of the steps for the
most common types of UserProfile and Realm settings. We refer to this as the
`property_types` framework. However, it is valuable to understand
the flow of events even if the `property_types` framework means you don't
have to write much code for a new setting.

**Database interaction:** Add any necessary code for updating and
interacting with the database in `zerver/lib/actions.py`. It should
update the database and send an event announcing the change.

**Application state:** Modify the `fetch_initial_state_data` and
`apply_event` functions in `zerver/lib/events.py` to update the state
based on the event you just created.

**Backend implementation:** Make any other modifications to the backend
required for your feature to do what it's supposed to do (this will
be unique to the feature you're implementing).

**New views:** Add any new application views to `zproject/urls.py`, or
update the appropriate existing view in `zerver/views/`. This
includes both views that serve HTML (new pages on Zulip) as well as new
API endpoints that serve JSON-formatted data.

**Testing:** At the very least, add a test of your event data flowing
through the system in `test_events.py` and an API test (e.g. for a
Realm setting, in `test_realm.py`).

### Frontend changes

**JavaScript:** Zulip's JavaScript is located in the directory
`static/js/`. The exact files you may need to change depend on your
feature. If you've added a new event that is sent to clients, be sure to
add a handler for it in `static/js/server_events_dispatch.js`.

**CSS:** The primary CSS file is `static/styles/zulip.css`. If your new
feature requires UI changes, you may need to add additional CSS to this
file.

**Templates:** The initial page structure is rendered via Jinja2
templates located in `templates/zerver`. For JavaScript, Zulip uses
Handlebars templates located in `static/templates`. Templates are
precompiled as part of the build/deploy process.

Zulip is fully internationalized, so when writing both HTML templates
or JavaScript code that generates user-facing strings, be sure to
[tag those strings for translation](translating.html).

**Testing:** There are two types of frontend tests: node-based unit
tests and blackbox end-to-end tests. The blackbox tests are run in a
headless browser using Casper.js and are located in
`frontend_tests/casper_tests/`. The unit tests use Node's `assert`
module are located in `frontend_tests/node_tests/`. For more
information on writing and running tests, see the
[testing documentation](testing.html).

### Documentation changes

After implementing the new feature, you should
document it and update any existing documentation that might be
relevant to the new feature. For more information on the kinds of
documentation Zulip has, see [Documentation](README.html).

## Example Feature

This example describes the process of adding a new setting to Zulip: a
flag that allows an admin to require topics on stream messages (the default
behavior is that topics can have no subject). This flag is an
actual Zulip feature. You can review [the original commit](
https://github.com/zulip/zulip/pull/5660/commits/aeeb81d3ff0e0cc201e891cec07e1d2cd0a2060d)
in the Zulip repo. (This commit displays the work of setting up a checkbox
for the feature on the admin settings page, communicating and saving updates
to the setting to the database, and updating the state of the application
after the setting is updated. For the code that accomplishes the underlying
task of requiring messages to have a topic, you can [view this commit](
https://github.com/zulip/zulip/commit/90e2f5053f5958b44ea9b2362cadcb076deaa975).)

### Update the model

First, update the database and model to store the new setting. Add a new
boolean field, `mandatory_topics`, to the Realm model in
`zerver/models.py`.

``` diff

# zerver/models.py

class Realm(ModelReprMixin, models.Model):
    # ...
    restricted_to_domain = models.BooleanField(default=True) # type: bool
    invite_required = models.BooleanField(default=False) # type: bool
+   mandatory_topics = models.BooleanField(default=False) # type: bool
```

The Realm model also contains an attribute, `property_types`, which
other backend functions use to handle most realm settings without any custom
code for the setting (more on this process below). The attribute is a
dictionary, where the key is the name of the realm field and the value
is the field's type. Add the new field to the `property_types`
dictionary.

``` diff

# zerver/models.py

class Realm(ModelReprMixin, models.Model)
  # ...
  # Define the types of the various automatically managed properties
    property_types = dict(
        add_emoji_by_admins_only=bool,
        allow_edit_history=bool,
        # ...
+       mandatory_topics=bool,
        # ...
```

**The majority of realm settings can be included in
`property_types`.**  However, there are some properties that need custom
logic and thus cannot use this framework.  For example:

* The realm `authentication_methods` attribute is a bitfield and needs
additional code for validation and updating.
* The `allow_message_editing` and `message_content_edit_limit_seconds`
fields depend on one another, so they are also handled separately and
not included in `property_types`.

When creating a realm property that is not a boolean, Text or
integer field, or when adding a field that is dependent on other fields,
do not add the field to the `property_types` dictionary. The steps
below will point out where to write additional code for these cases.

### Create the migration

Create the migration file: `./manage.py makemigrations`. Make sure to
commit the generated file to git:
`git add zerver/migrations/NNNN_realm_mandatory_topics.py`
(NNNN is a number that is equal to the number of migrations.)

If you run into problems, the
[Django migration documentation](https://docs.djangoproject.com/en/1.8/topics/migrations/)
is helpful.

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
  Applying zerver.NNNN_realm_mandatory_topics... OK
```

Once you've run the migration, restart memcached on your development
server (`/etc/init.d/memcached restart`) and then [restart the development server](
http://zulip.readthedocs.io/en/latest/dev-remote.html?highlight=tools%2Frun-dev.py#running-the-development-server)
to avoid interacting with cached objects.

### Handle database interactions

Next, we will implement the backend part of this feature.
Like typical apps, we will need our backend to update the database and
send some response to the client that made the request.

Beyond that, we need to orchestrate notifications about the setting change
to *other* clients (or other users, if you will).  Clients
find out about settings through two closely related code paths. When a client
first contacts the server, the server sends the client its
initial state. Subsequently, clients subscribe to "events," which can
(among other things) indicate that settings have changed.

For the backend piece, we will need our action to make a call to `send_event`
to send the event to clients that are active. We will also need to
modify `fetch_initial_state_data` so that the new field is passed to
clients. See [our event system docs](events-system.html) for all the
gory details.

Anyway, getting back to implementation details...

If you are working on a feature that is in the realm `property_types`
dictionary, you will not need to add code to `zerver/lib/actions.py`, but
we will describe what the process in that file does:

In `zerver/lib/actions.py`, the function `do_set_realm_property` takes
in the name of a realm property to update and the value it should
have. This function updates the database and triggers an event to
notify clients about the change. It uses the field's type, specified
in the `Realm.property_types` dictionary, to validate the type of the
value before updating the property; this is primarily an assertion to
help catch coding mistakes, not to check for bad user input.

After updating the given realm field, `do_set_realm_property` creates
an 'update' event with the name of the property and the new value. It
then calls `send_event`, passing the event and the list of users whose
browser sessions should be notified as the second argument. The latter
argument can be a single user (if the setting is a personal one, like
time display format), members in a particular stream only or all
active users in a realm.

    # zerver/lib/actions.py

    def do_set_realm_property(realm, name, value):
      # type: (Realm, str, Union[Text, bool, int]) -> None
      """Takes in a realm object, the name of an attribute to update, and the
      value to update.
      """
      property_type = Realm.property_types[name]
      assert isinstance(value, property_type), (
          'Cannot update %s: %s is not an instance of %s' % (
              name, value, property_type,))

      setattr(realm, name, value)
      realm.save(update_fields=[name])
      event = dict(
          type='realm',
          op='update',
          property=name,
          value=value,
      )
      send_event(event, active_user_ids(realm))

If the new realm property being added does not fit into the
`property_types` framework (such as the `authentication_methods`
field), you'll need to create a new function to explicitly update this
field and send an event. For example:

    # zerver/lib/actions.py

    def do_set_realm_authentication_methods(realm, authentication_methods):
        # type: (Realm, Dict[str, bool]) -> None
        for key, value in list(authentication_methods.items()):
            index = getattr(realm.authentication_methods, key).number
            realm.authentication_methods.set_bit(index, int(value))
        realm.save(update_fields=['authentication_methods'])
        event = dict(
            type="realm",
            op="update_dict",
            property='default',
            data=dict(authentication_methods=realm.authentication_methods_dict())
        )
        send_event(event, active_user_ids(realm))

### Update application state

`zerver/lib/events.py` contains code to ensure that your new setting is included
in the data sent down to clients: both when a new client is loaded
and when changes happen. This file also automatically
handles realm settings in the `property_types` dictionary, so you would
not need to change this file if your setting fits that framework.

The `fetch_initial_state_data` function is responsible for sending data when
a client is loaded (data added to the `state` here will be available both
in `page_params` in the browser, as well as to API clients like the mobile
apps). The `apply_event` function in `zerver/lib/events.py` is important for
making sure the `state` is always correct, even in the event of rare
race conditions.

    # zerver/lib/events.py

    def fetch_initial_state_data(user_profile, event_types, queue_id, include_subscribers=True):
      # ...
      if want('realm'):
        for property_name in Realm.property_types:
            state['realm_' + property_name] = getattr(user_profile.realm, property_name)
        state['realm_authentication_methods'] = user_profile.realm.authentication_methods_dict()
        state['realm_allow_message_editing'] = user_profile.realm.allow_message_editing
        # ...

    def apply_event(state, events, user_profile, include_subscribers):
      for event in events:
        # ...
        elif event['type'] == 'realm':
           field = 'realm_' + event['property']
           state[field] = event['value']
           # ...

If your new realm property fits the `property_types`
framework, you don't need to change `fetch_initial_state_data` or
`apply_event`. However, if you are adding a
property that is handled separately, you will need to explicitly add
the property to the `state` dictionary in the `fetch_initial_state_data`
function. E.g., for `authentication_methods`:

    # zerver/lib/events.py

    def fetch_initial_state_data(user_profile, event_types, queue_id, include_subscribers=True):
      # ...
      if want('realm'):
          # ...
          state['realm_authentication_methods'] = user_profile.realm.authentication_methods_dict()
          # ...

For this setting, one won't need to change `apply_event` since its
default code for `realm` event types handles this case correctly, but
for a totally new type of feature, a few lines in that function may be
needed.

### Add a new view

You will need to add a view for clients to access that will call the
`actions.py` code to update the database. This example feature
adds a new parameter that will be sent to clients when the
application loads and should be accessible via JavaScript. There is
already a view that does this for related flags: `update_realm` in
`zerver/views/realm.py`. So in this case, we can add our code to the
existing view instead of creating a new one.

You'll need to add a parameter for the new field to the `update_realm`
function in `zerver/views/realm.py` (and add the appropriate mypy type
annotation).

``` diff

# zerver/views/realm.py

def update_realm(request, user_profile, name=REQ(validator=check_string, default=None),
             # ...,
+            mandatory_topics=REQ(validator=check_bool, default=None),
             # ...):
+            # type: (HttpRequest, UserProfile, ..., Optional[bool], ...
  # ...
```

If this feature fits the `property_types` framework and does
not require additional validation, this is the only change to make
to `zerver/views/realm.py`.

Text fields or other realm properties that need additional validation
can be handled at the beginning of `update_realm`.

    # zerver/views/realm.py

    # Additional validation/error checking beyond types go here, so
    # the entire request can succeed or fail atomically.
    if default_language is not None and default_language not in get_available_language_codes():
        raise JsonableError(_("Invalid language '%s'" % (default_language,)))
    if description is not None and len(description) > 100:
        return json_error(_("Realm description cannot exceed 100 characters."))
    # ...

The code in `update_realm` loops through the `property_types` dictionary
and calls `do_set_realm_property` on any property to be updated from
the request.

If the new feature is not in `property_types`, you will need to write code
to call the function you wrote in `actions.py` that updates the database
with the new value. E.g., for `authentication_methods`, we created
`do_set_realm_authentication_methods`, which we will call here:

    # zerver/views/realm.py

    # import do_set_realm_authentication_methods from actions.py
    from zerver.lib.actions import (
        do_set_realm_message_editing,
        do_set_realm_authentication_methods,
        # ...
    )
    # ...
    # ...
    if authentication_methods is not None and realm.authentication_methods_dict() != authentication_methods:
            do_set_realm_authentication_methods(realm, authentication_methods)
            data['authentication_methods'] = authentication_methods
    # ...

This completes the backend implementation. A great next step is to
write the [backend tests](testing-with-django.html).

### Backend Tests

To test the new setting syncs correctly with the `property_types`
framework, one usually just needs to add a line in each of
`test_events.py` and `test_realm.py` with a list of values to switch
between in the test.  In the case of a boolean field, no action is
required, because those tests will correctly assume that the only
values to test are `True` and `False`.

In `test_events.py`, the function that runs tests for the `property_types`
framework is `do_set_realm_property_test`, and in `test_realm.py`, it is
`do_test_realm_update_api`.

One still needs to add a test for whether the setting actually
controls the feature it is supposed to control, however.

### Update the front end

After completing the process of adding a new feature on the back end,
you should make the required front end changes: in this case, a checkbox needs
to be added to the admin page (and its value added to the data sent back
to server when a realm is updated) and the change event needs to be
handled on the client.

To add the checkbox to the admin page, modify the relevant template,
`static/templates/settings/organization-permissions-admin.handlebars`
(omitted here since it is relatively straightforward).

Then add the new form control in `static/js/admin.js`.

``` diff

// static/js/admin.js

function _setup_page() {
    var options = {
        realm_name: page_params.realm_name,
        realm_description: page_params.realm_description,
        realm_restricted_to_domain: page_params.realm_restricted_to_domain,
        realm_invite_required: page_params.realm_invite_required,
        // ...
+       realm_mandatory_topics: page_params.mandatory_topics,
        // ...
```

The JavaScript code for organization settings and permissions can be found in
`static/js/settings_org.js`.

There is a front-end version of `property_types`, which reduces the code
needed on the front end for a new feature.

Add the new feature to the `property_types` object in `settings_org.js`.
The key should be the setting name and the value should be an object with
the following keys:

* type
* checked_msg (what message the user sees when they enable the setting)
* unchecked_msg (what message the user sees when they disable the setting)

``` diff

// static/js/settings_org.js

var property_types = {
    settings: {
        // ...
    },
    permissions: { // ...
+       mandatory_topics: {
+           type: 'bool',
+           checked_msg: i18n.t("Topics are required in messages to streams"),
+           unchecked_msg: i18n.t("Topics are not required in messages to streams"),
        },
    },
};
```

Additionally, any code needed to update the UI when the setting is changed
should be written in a function inside `settings_org.js`.
For example, when a realm description is updated, that value change should
occur in other windows where the description field is visible:

    # static/js/settings_org.js

    exports.update_realm_description = function () {
        if (!meta.loaded) {
            return;
        }

        $('#id_realm_description').val(page_params.realm_description);
    };


This ensures the appropriate code will run even if the
changes are made in another browser window.

In the example of updating a `mandatory_topics` setting, most of the changes
are on the backend, so no UI updates are required.

Finally, update `server_events_dispatch.js` to handle related events coming from
the server. There is an object, `realm_settings`, in the function
`dispatch_normal_event`. The keys in this object are setting names and the
values are the UI updating functions to run when an event has occurred.

If there is no relevant UI change to make, the value should be `noop`
(this is the case for `mandatory_topics`). However, if you had written
a function in `settings_org.js` to update UI, that function should
be the value in the `realm_settings` object.

``` diff

// static/js/server_events_dispatch.js

function dispatch_normal_event(event) {
    switch (event.type) {
    // ...
    case 'realm':
      var realm_settings = {
          add_emoji_by_admins_only: settings_emoji.update_custom_emoji_ui,
          allow_edit_history: noop,
          // ...
+         mandatory_topics: noop,
          // ...
      };
```

The rest of the `dispatch_normal_events` function updates the state of the
application if an update event has occurred on a realm property and runs
the associated function to update the application's UI, if necessary.

### Front End Tests

A great next step is to write front end tests. There are two types of
frontend tests: [node-based unit tests](testing-with-node.html) and
[Casper end-to-end tests](testing-with-casper.html).

At the minimum, if you created a new function to update UI in
`settings_org.js`, you will need to mock that function in
`frontend_tests/node_tests/dispatch.js`. Add the name of the UI
function you created to the following object with `noop` as the value:

    # frontend_tests/node_tests/dispatch.js

    set_global('settings_org', {
        reset_realm_default_language: noop,
        toggle_email_change_display: noop,
        toggle_name_change_display: noop,
        update_message_retention_days: noop,
        update_realm_description: noop,
    });

Beyond that, you should add any applicable tests that verify the
behavior of the setting you just created.

### Update documentation

After you add a new view, you should document your feature. This
feature adds new functionality that requires messages to have topics
if the setting is enabled. A recommended way to document this feature
would be to update and/or augment
[Zulip's user documentation](https://chat.zulip.org/help/)
to reflect your changes and additions.

At the very least, this will involve adding (or modifying) a Markdown file
documenting the feature to `templates/zerver/help/` in the main Zulip
server repository, where the source for Zulip's user documentation is
stored. For information on writing user documentation, see
[Zulip's general user guide documentation](user-docs.html).

For a more concrete example of writing documentation for a new feature, see
[an example commit in the Zulip repo](
https://github.com/zulip/zulip/commit/5b4d9774e02a45e43465b0a28ffb3d9b373c9098)
that documented a new realm feature, [the current source](
https://github.com/zulip/zulip/blob/master/templates/zerver/help/only-allow-admins-to-invite-new-users.md),
and [the final rendered documentation](
https://chat.zulip.org/help/only-allow-admins-to-invite-new-users).
