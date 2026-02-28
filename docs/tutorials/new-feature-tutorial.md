# Writing a new application feature

The changes needed to add a new feature will vary, of course, but this
document provides a general outline of what you may need to do, as well
as an example of the specific steps needed to add a new feature: adding
a new option to the application that is dynamically synced through the
data system in real-time to all browsers the user may have open.

As you read this, you may find you need to learn about Zulip's
real-time push system; the
[real-time push and events](../subsystems/events-system.md)
documentation has a detailed explanation of how everything works. You
may also find it beneficial to read Zulip's
[architectural overview](../overview/architecture-overview.md).
Zulip is a web application built using the
[Django framework](https://www.djangoproject.com/), and some of the
processes listed in this tutorial, such as database migrations and
tests, use Django's tooling.

Zulip's [directory structure](../overview/directory-structure.md)
will also be helpful to review when creating a new feature. Many
aspects of the structure will be familiar to Django developers. Visit
[Django's documentation](https://docs.djangoproject.com/en/5.0/#index-first-steps)
for more information about how Django projects are typically
organized. And finally, the
[message sending](../subsystems/sending-messages.md) documentation on
the additional complexity involved in sending messages.

## General process

### Files impacted

This tutorial will walk through adding a new feature to a Realm (an
organization in Zulip). The following files are involved in the process:

**Backend**

- `zerver/models/realms.py`: Defines the database model.
- `zerver/views/realm.py`: Contains the view function that implements the
  API endpoint for editing Realm objects.
- `zerver/actions/realm_settings.py`: Contains code for updating and
  interacting with the database.
- `zerver/lib/events.py`: Ensures that the state Zulip sends to clients
  is always consistent and correct.

**Frontend**

- `web/src/state_data.ts`: Defines the expected state of the data that
  is received from the Zulip server.
- `web/templates/settings/organization_settings_admin.hbs`: Defines
  the structure of the organization settings admin modal.
- `web/src/admin.ts`: Handles building the organization settings admin
  modal.
- `web/src/settings_org.ts`: Handles form submission for changes to an
  organization's settings.
- `web/src/server_events_dispatch.js`: Handles events coming from the
  server.

**Backend testing**

- `zerver/tests/test_realm.py`: Contains end-to-end API tests for
  updating realm settings.
- `zerver/tests/test_events.py`: Tests for possible race bugs in the
  implementation of events.

**Frontend testing**

- `web/e2e-tests/admin.test.ts`: Contains end-to-end tests for the
  organization admin settings pages.
- `web/tests/dispatch.test.cjs`: Unit tests for handling of events.

**Documentation**

- `zerver/openapi/zulip.yaml`: Contains OpenAPI definitions for the
  Zulip REST API.
- `api_docs/changelog.md`: Documentation listing all changes to the
  Zulip Server API.
- `starlight_help/...`: The user-facing documentation (help center)
  for the application.

### Adding a field to the database

**Update the model:** The server accesses the underlying database in
`zerver/models/realms.py`. Add a new field in the appropriate class.

**Create and run the migration:** To create and apply a migration, run the
following commands:

```bash
./manage.py makemigrations
./manage.py migrate
```

It's highly recommended to read our
[database migration documentation](../subsystems/schema-migrations.md)
to learn more about creating and applying database migrations.

**Test your changes:** Once you've run the migration, [restart the
development
server](../development/remote.md#running-the-development-server).

### Backend changes

We have a framework that automatically handles many of the steps for the
most common types of UserProfile and Realm settings. We refer to this as the
`property_types` framework. However, it is valuable to understand
the flow of events even if the `property_types` framework means you don't
have to write much code for a new setting.

**Database interaction:** Add any necessary code for updating and
interacting with the database in `zerver/actions/realm_settings.py`.
It should update the database and send an event announcing the change.

**Application state:** Modify the `fetch_initial_state_data` and
`apply_event` functions in `zerver/lib/events.py` to update the state
based on the field you just created.

**Backend implementation:** Make any other modifications to the backend
required for your feature to do what it's supposed to do (this will
be unique to the feature you're implementing).

**New views:** Add any new application views to `zproject/urls.py`, or
update the appropriate existing view in `zerver/views/...`. This
includes both views that serve HTML (new pages on Zulip) as well as new
API endpoints that serve JSON-formatted data.

**Testing:** At the very least, add a test of your event data flowing
through the system in `test_events.py` and an API test (e.g., for a
Realm setting, in `test_realm.py`).

### Frontend changes

**JavaScript/TypeScript:** Zulip's JavaScript and TypeScript sources are
located in the directory `web/src/`. The exact files you may need to change
depend on your feature. If you've added a new event that is sent to clients,
be sure to add a handler for it in `web/src/server_events_dispatch.js`.

**CSS:** The primary CSS file is `web/styles/zulip.css`. If your new
feature requires UI changes, you may need to add additional CSS to this
file.

**Templates:** The initial page structure is rendered via Jinja2
templates located in `templates/zerver/app`. For JavaScript, Zulip uses
Handlebars templates located in `web/templates`. Templates are
precompiled as part of the build/deploy process.

Zulip is fully internationalized, so when writing both HTML templates
or JavaScript/TypeScript/Python code that generates user-facing strings,
be sure to [tag those strings for translation](../translating/translating.md).

**Testing:** There are two types of frontend tests: node-based unit
tests and blackbox end-to-end tests. The blackbox tests are run in a
headless Chromium browser using Puppeteer and are located in
`web/e2e-tests/`. The unit tests use Node's `assert` module are located
in `web/tests/`. For more information on writing and running tests, see
the [testing documentation](../testing/testing.md).

### Documentation changes

After implementing the new feature, you should document it and update
any existing documentation that might be relevant to the new feature.
For detailed information on the kinds of documentation Zulip has, see
[Documentation](../documentation/overview.md).

**Help center documentation:** You will likely need to at least update,
extend and link to articles in the `starlight_help/` directory that are
related to your new feature. [Writing help center articles](../documentation/helpcenter.md)
provides more detailed information about writing and editing feature
`starlight_help/` directory articles.

**API documentation:** A new feature will probably impact the REST API
documentation as well, which will mean updating `zerver/openapi/zulip.yaml`
and modifying `api_docs/changelog.md` for a new feature
level. [Documenting REST API endpoints](../documentation/api.md)
explains Zulip's API documentation system and provides a step by step
guide to adding or updating documentation for an API endpoint.

## Example feature

This example describes the process of adding a new realm setting to Zulip.
For the purposes of this tutorial, this new setting will be called
`my_fantastic_feature`.

:::{tip}

A useful tool that we'll highlight throughout this tutorial is
`git-grep`. If you're unfamiliar with using `git-grep`, then check out
[this blog post](https://laurynmm.github.io/2021/12/22/git-grep.html)
for an introduction to it, as well as the [official `git-grep`
documentation](https://git-scm.com/docs/git-grep.)

:::

### Update the model

First, update the database and model to store the new setting. Add a new
boolean field, `my_fantastic_feature`, to the Realm model in
`zerver/models/realms.py`.

```diff
 # zerver/models/realms.py

 class Realm(models.Model):
     # ...
     require_unique_names = models.BooleanField(default=False)
     name_changes_disabled = models.BooleanField(default=False)
     email_changes_disabled = models.BooleanField(default=False)
     avatar_changes_disabled = models.BooleanField(default=False)

+    # My fantastic feature for the new feature tutorial.
+    my_fantastic_feature = models.BooleanField(default=False)
```

The Realm model also contains an attribute, `property_types`, which
other backend functions use to handle most realm settings without any
custom code for the setting (more on this process below). The attribute
is a dictionary, where the key is the name of the realm field and the
value is the field's type. Add the new field to the `property_types`
dictionary.

```diff
 # zerver/models/realms.py

 class Realm(models.Model)
     # ...
     # Define the types of the various automatically managed properties
     property_types: dict[str, type | UnionType] = dict(
         allow_message_editing=bool,
         avatar_changes_disabled=bool,
         # ...
+        my_fantastic_feature=bool,
         # ...
```

**The majority of realm settings can be included in `property_types`.**
However, there are some properties that need custom logic and thus cannot
use this framework. Any properties that define a relationship to another
model (e.g., a `ForeignKey` field) do not use the `property_types`
framework, for example `moderation_request_channel` property and the
`can_add_custom_emoji_group` property.

When creating a realm property that is not a boolean, character or
integer field, or when adding a field that is dependent on other fields,
do not add the field to the `property_types` dictionary. The steps below
will point out where to write additional code for these cases.

### Create the migration

Create the migration file using the Django `makemigrations` command:
`./manage.py makemigrations`. Make sure to commit the generated file to
git: `git add zerver/migrations/NNNN_my_fantastic_feature.py` (NNNN is a
number that is equal to the current number of migrations.)

If you run into problems, the
[Django migration documentation](https://docs.djangoproject.com/en/5.0/topics/migrations/)
is helpful.

### Test your migration changes

Apply the migration using Django's `migrate` command, `./manage.py migrate`:

```console
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
  Applying zerver.NNNN_my_fantastic_feature... OK
```

Once you've run the migration, [restart the development
server](../development/remote.md#running-the-development-server).

### Handle database interactions

Next, we will implement the backend part of this feature. Like typical
apps, we will need our backend to update the database and send some
response to the client that made the request.

Beyond that, we need to orchestrate notifications about the setting
change to _other_ clients (or other users, if you will). Clients find out
about settings through two closely related code paths. When a client
first contacts the server, the server sends the client its initial state.
Subsequently, clients subscribe to "events," which can (among other
things) indicate that settings have changed.

For the backend piece, we will need our action to make a call to
`send_event_on_commit` to send the event to clients that are active
(The event is only sent after the current database transaction
commits, hence the name). We will also need to modify
`fetch_initial_state_data` so that the new field is passed to
clients. See [our event system docs](../subsystems/events-system.md)
for all the gory details.

Getting back to implementation details...

If you are working on a feature that is in the realm `property_types`
dictionary, you will not need to add code to
`zerver/actions/realm_settings.py`, but we will describe what the
process in that file does:

In `zerver/actions/realm_settings.py`, the function `do_set_realm_property`
takes in the name of a realm property to update and the value it should
have. This function updates the database and triggers an event to
notify clients about the change. It uses the field's type, specified
in the `Realm.property_types` dictionary, to validate the type of the
value before updating the property; this is primarily an assertion to
help catch coding mistakes, not to check for bad user input.

After updating the given realm field, `do_set_realm_property` creates
an 'update' event with the name of the property and the new value. It
then calls `send_event_on_commit`, passing the event and the list of
users whose browser sessions should be notified as the second argument.
The latter argument can be a single user (if the setting is a personal
one, like time display format), members in a particular channel only or
all active users in an realm.

:::{tip}

Use git-grep to find and read the `do_set_realm_property`
function. Are there `property_types` that are handled differently in
that function? Which ones? Does the function indicate why?

:::

If the new realm property being added does not fit into the
`property_types` framework (such as the `moderation_request_channel`
field), you'll need to create a new function to explicitly update this
field and send an event. For example:

```python
# zerver/actions/realm_settings.py

def do_set_realm_stream(
    realm: Realm,
    field: Literal[
        "moderation_request_channel",
        "new_stream_announcements_stream",
        "signup_announcements_stream",
        "zulip_update_announcements_stream",
    ],
    stream: Stream | None,
    stream_id: int,
    *,
    acting_user: UserProfile | None,
) -> None:
    # We could calculate more of these variables from `field`, but
    # it's probably more readable to not do so.
    if field == "moderation_request_channel":
        old_value = realm.moderation_request_channel_id
        realm.moderation_request_channel = stream
        property = "moderation_request_channel_id"
```

### Update application state

`zerver/lib/events.py` contains code to ensure that your new setting is
included in the data sent down to clients: both when a new client is
loaded and when changes happen. This file also automatically handles
realm settings in the `property_types` dictionary, so you would not need
to change this file if your setting fits that framework.

The `fetch_initial_state_data` function is responsible for sending data
when a client is loaded (data added to the `state` here will be available
both in `page_params` in the browser, as well as to API clients like the
mobile app). The `apply_event` function in `zerver/lib/events.py` is
important for making sure the `state` is always correct, even in the
event of rare race conditions.

```python
# zerver/lib/events.py

def fetch_initial_state_data(
    user_profile: UserProfile | None,
    # ...
    if want("realm"):
        # The realm bundle includes both realm properties and server
        # properties, since it's rare that one would want one and not
        # the other. We expect most clients to want it.
        # ...
        for property_name in Realm.property_types:
            state["realm_" + property_name] = getattr(realm, property_name)

        for setting_name in Realm.REALM_PERMISSION_GROUP_SETTINGS:
            setting_group_id = getattr(realm, setting_name + "_id")
            state["realm_" + setting_name] = get_group_setting_value_for_register_api(
                setting_group_id, anonymous_group_membership_data_dict
            )
        # ...

def apply_event(
    user_profile: UserProfile,
    # ...
) -> None:
    # ...
    elif event["type"] == "realm":
        if event["op"] == "update":
            field = "realm_" + event["property"]
            state[field] = event["value"]
           # ...
```

If your new realm property fits the `property_types` framework, you don't
need to change `fetch_initial_state_data` or `apply_event`. However, if
you are adding a property that is handled separately, you will need to
explicitly add the property to the `state` dictionary in the
`fetch_initial_state_data` function.

For our example, one won't need to change `apply_event` since its default
code for `realm` event types handles this case correctly, but for a
totally new type of feature, a few lines in that function may be needed.

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

```diff
 # zerver/views/realm.py

@require_realm_admin
@typed_endpoint
def update_realm(
    request: HttpRequest,
    user_profile: UserProfile,
     *,
     allow_message_editing: Json[bool] | None = None,
     authentication_methods: Json[dict[str, Any]] | None = None,
     # ...
+    my_fantastic_feature: Json[bool] | None = None,
     # ...
 ):
     # ...
```

If this feature fits the `property_types` framework and does not
require additional validation, this is the only change to make to
`zerver/views/realm.py`.

Text fields or other realm properties that need additional validation
can be handled at the beginning of `update_realm`.

```python
# zerver/views/realm.py

    # Additional validation/error checking beyond types go here, so
    # the entire request can succeed or fail atomically.
    if default_language is not None and default_language not in get_available_language_codes():
        raise JsonableError(_("Invalid language '{language}'").format(language=default_language))
# ...
```

The code in `update_realm` loops through the `property_types` dictionary
and calls `do_set_realm_property` on any property to be updated from
the request.

If the new feature is not in `property_types`, you will need to write code
to call the function you wrote in `actions.py` that updates the database
with the new value. E.g., for `moderation_request_channel`, we created
`do_set_realm_moderation_request_channel`, which we will call here:

```python
# zerver/views/realm.py

# import do_set_realm_authentication_methods from actions.py
from zerver.actions.realm_settings import (
    # ...
    do_set_realm_moderation_request_channel,
    # ...
)
# ...
# ...
    # Channel-valued settings are not yet fully supported by the
    # property_types framework, and thus have explicit blocks here.
    if moderation_request_channel_id is not None and (
        realm.moderation_request_channel is None
        or realm.moderation_request_channel.id != moderation_request_channel_id
    ):
        new_moderation_request_channel_id = None
        if moderation_request_channel_id >= 0:
            (new_moderation_request_channel_id, sub) = access_stream_by_id(
                user_profile, moderation_request_channel_id, require_content_access=False
            )
        do_set_realm_moderation_request_channel(
            realm,
            new_moderation_request_channel_id,
            moderation_request_channel_id,
            acting_user=user_profile,
        )
        data["moderation_request_channel_id"] = moderation_request_channel_id
# ...
```

This completes the backend implementation. A great next step is to
write automated backend tests for your new feature.

### Backend tests

To test the new setting syncs correctly with the `property_types`
framework, one usually just needs to add a line in each of
`zerver/tests/test_events.py` and `zerver/tests/test_realm.py` with a
list of values to switch between in the test. In the case of a boolean
field, no action is required, because those tests will correctly assume
that the only values to test are `True` and `False`.

In `test_events.py`, the function that runs tests for the `property_types`
framework is `do_set_realm_property_test`, and in `test_realm.py`, it is
`do_test_realm_update_api`.

One would still need to add tests for whether the setting actually
controls the feature it is supposed to control. At this time, our example,
`my_fantastic_feature`, does not change any behavior on the backend, so
we don't need to add any additional tests. If you're using this tutorial
as a guide for creating an actual new feature, then at this point you
should add any necessary backend tests.

Visit Zulip's [Django testing](../testing/testing-with-django.md)
documentation to learn more about the backend testing framework.

:::{tip}

Pick one of the other `Realm.property_types` settings and
use `git-grep` to find examples of backend tests that were written for
that setting: `git grep REALM_SETTING zerver/tests/`.

:::

Also note that you may already need to update the API documentation for
your new feature to pass new or existing backend tests at this point.
The tutorial for [writing REST API endpoints](../documentation/api.md)
can be a helpful resource, especially the section on [debugging schema
validation errors](../documentation//api.md#debugging-schema-validation-errors).

### What is my fantastic feature?

Since you've now set up the backend for your new fantastic feature, let's
take a moment to discuss what that feature actually will be. Here's where
you get to be creative!

Think of some fun, visual change that you could make to the Zulip web app
in your development environment. Maybe toggling `my_fantastic_feature` will
change the app font to [Dingbats](https://en.wikipedia.org/wiki/Dingbat).
Maybe it will change the color of the font in the message feed. Maybe it
will make all user status emoji render upside down 🙃. That's up to you!

The next part of this tutorial will go through the process of setting up
the toggle for turning your feature on and off via the organization
settings admin modal in the web-app. After that, your final challenge will
be to make the changes to the codebase to make your fantastic idea into a
reality in your development environment.

### Update the frontend

After completing the process of adding a new realm setting on the backend,
you'll want make the required frontend changes.

Since we've updated the data sent for a realm to include a new property,
we need to update the `realm_schema` on the frontend to match our changes
in `zerver/lib/events.py`. This can be done in `web/src/state_data.ts`:

```diff
 // web/src/state_data.ts

 // Sync this with zerver.lib.events.do_events_register.
 export const realm_schema = z.object({
     // ...
     realm_move_messages_within_stream_limit_seconds: z.nullable(z.number()),
+    realm_my_fantastic_feature: z.boolean(),
     realm_name_changes_disabled: z.boolean(),
     // ...
```

In order for an admin user to enable and disable our new realm setting, a
checkbox needs to be added to the organization settings page (and its
value added to the data sent back to server when a realm is updated) and
the change event needs to be handled on the client.

To add the checkbox to the organization settings admin modal, you'll need
to modify one of the templates for the organization settings modal:
`web/templates/settings/organization...`. If you're adding a non-checkbox
field, you'll need to specify the type of the field via the
`data-setting-widget-type` attribute in the Handlebars template.

For simplicity, let's add the checkbox for `realm_my_fantastic_feature` to
the "Message feed" section in `web/templates/settings/organization_settings_admin.hbs`.
Since there are a number of realm settings controlled via checkbox, there
is a `settings_checkbox` partial template already set up for you to reuse.

:::{tip}

Use `git-grep` to see where the other realm settings in the
"Message feed" section of that template are in the `web/` directory.

Also, if you're not familiar with the organization settings modal, log in
as Iago in your development environment and follow the Zulip help center
instructions for [customizing organization settings](https://zulip.com/help/customize-organization-settings).

:::

Then add the new form control in `web/src/admin.ts`.

```diff
 // web/src/admin.ts

 export function build_page() {
     const options = {
        custom_profile_field_types: realm.custom_profile_field_types,
        full_name: current_user.full_name,
         // ...
+        realm_my_fantastic_feature: realm.realm_my_fantastic_feature,
         // ...
```

You'll also want to add a label to the `admin_settings_label` object
in that same file. Note that these labels are marked for
[translation](../translating/internationalization.md).

Finally, update `server_events_dispatch.js` to handle related events
coming from the server. There is an object, `realm_settings`, in the
function `dispatch_normal_event`. The keys in this object are setting
names and the values are the UI updating functions to run when an event
has occurred.

If there is no relevant UI change to make other than in settings page
itself, the value should be `noop`. However, if you are writing a
function to update the UI after a given setting has changed, your
function should be referenced in the `realm_settings` of
`server_events_dispatch.js`. See for example
`settings_emoji.update_custom_emoji_ui`.

```diff
 // web/src/server_events_dispatch.js

 function dispatch_normal_event(event) {
     switch (event.type) {
     // ...
     case 'realm':
         var realm_settings = {
             add_custom_emoji_policy: settings_emoji.update_custom_emoji_ui,
             allow_edit_history: noop,
             // ...
+            my_fantastic_feature: ???,
             // ...
         };
```

Checkboxes and other common input elements handle the UI updates
automatically through the logic in `settings_org.sync_realm_settings`.

The rest of the `dispatch_normal_events` function updates the state of the
application if an update event has occurred on a realm property and runs
the associated function to update the application's UI, if necessary.

Now that you've got the admin checkbox set up to toggle your new feature
on and off, you should work on implementing your fantastic idea! Remember
to use `git-grep` to help as you become familiar with the codebase.

### Manually test

Here are few important cases you should consider when manually testing
your changes:

- For organization settings where we have a "save/discard" model, make
  sure both the "Save" and "Discard changes" buttons are working
  properly when toggling the realm setting.

- If your setting is dependent on another setting, carefully check
  that both are properly synchronized. For example, the input element
  for `realm_waiting_period_threshold_custom_input` is shown only when
  we have selected the custom time limit option in the
  `realm_waiting_period_threshold` dropdown.

- Do some manual testing for the real-time synchronization of input
  elements across the browsers and just like "Discard changes" button,
  check whether dependent settings are synchronized properly (this is
  easy to do by opening two browser windows to the settings page, and
  making changes in one while watching the other).

- Each subsection has independent "Save" and "Discard changes"
  buttons, so changes and saving in one subsection shouldn't affect
  the others.

### Frontend tests

A great next step is to write frontend tests. There are two types of
frontend tests: [node-based unit tests](../testing/testing-with-node.md) and
[Puppeteer end-to-end tests](../testing/testing-with-puppeteer.md).

At the minimum, you'll want to update `web/tests/lib/example_realm.cjs`
for the new realm setting that you've added.

Beyond that, you should add any applicable tests that verify the
behavior of the setting you just created.

:::{tip}

If you've identified a similar feature on the frontend to the
one that you're creating, use your `git-grep` skills to find and read
through the frontend tests for that feature.

:::

### Update documentation

If you're using this tutorial as a guide to add an actual new feature to
Zulip, it's really important to make sure that your new feature is well
documented.

A recommended way to document a new feature is to update and/or augment
Zulip's existing [help center documentation](https://zulip.com/help/)
to reflect your changes and additions.

At the very least, this will involve modifying (or adding) a Markdown
file documenting the feature in the `starlight_help/` directory of the
main Zulip server repository, where the source for Zulip's end user
documentation is stored. Details about writing, editing and testing these
files can be found in:
[Writing help center articles](../documentation/helpcenter.md).

Also, new features will often impact Zulip's REST API documentation,
which is found in `zerver/openapi/zulip.yaml`. You may have noticed
this during the testing process as the Zulip test suite should fail if
there is a change to the API without a corresponding update to the
documentation.

The best way to understand writing and updating Zulip's API
documentation is to read more about Zulip's
[REST API documentation process](../documentation/api.md)
and [OpenAPI configuration](../documentation/openapi.md).

In particular, if there is an API change, you should use the
`create-api-changelog` tool to create a file for the API changelog
entry for your your new feature. The API feature level allows the
developers of mobile clients and other tools using the Zulip API to
programmatically determine whether the Zulip server they are
interacting with supports a given feature; see the
[Zulip release lifecycle](../overview/release-lifecycle.md).

### Share your fantastic feature

If you're using this tutorial to learn about the codebase and have
created a fun, fantastic feature, share a screenshot and/or a GIF
from your development environment of your unique changes to the
web-app UI in the Zulip development community's
[new members](https://chat.zulip.org/#topics/channel/95-new-members)
channel!
