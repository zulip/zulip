# Writing views in Zulip

## What this covers

This page documents how views work in Zulip. You may want to read the
[new feature tutorial](new-feature-tutorial.md)
and treat this as a reference.

If you have experience with Django, much of this will be familiar, but
you may want to read about how REST requests are dispatched, and how
request authentication works.

This document supplements the [new feature tutorial](new-feature-tutorial.md)
and the [testing](../testing/testing.md)
documentation.

## What is a view?

A view in Zulip is everything that helps implement a server endpoint.
Every path that the Zulip server supports (doesn't show a 404 page
for) is a view. The obvious ones are those you can visit in your
browser, for example
[/integrations](https://zulip.com/integrations/), which shows the
integration documentation. These paths show up in the address bar of
the browser. There are other views that are only seen by software,
namely the API views. They are used to build the various clients that
Zulip has, namely the web client (which is also used by the desktop
client) and the mobile clients.

## Modifying urls.py

A view is anything with an entry in the appropriate urls.py, usually
`zproject/urls.py`. Zulip views either serve HTML (pages for browsers)
or JSON (data for Zulip clients on all platforms, custom bots, and
integrations).

The format of the URL patterns in Django is [documented
here](https://docs.djangoproject.com/en/3.2/topics/http/urls/), and
the Zulip specific details for these are discussed in detail in the
[life of a request doc](life-of-a-request.md#options).

We have two Zulip-specific conventions we use for internationalization and for
our REST API, respectively.

## Writing human-readable views

If you're writing a new page for the website, make sure to add it
to `i18n_urls` in `zproject/urls.py`

```diff
     i18n_urls = [
     ...
+    path('quote-of-the-day', TemplateView.as_view(template_name='zerver/qotd.html')),
+    path('postcards', 'zerver.views.postcards'),
]
```

As an example, if a request comes in for Spanish, language code `es`,
the server path will be something like: `es/features/`.

### Decorators used for webpage views

This section documents a few simple decorators that we use for webpage
views, as an introduction to view decorators.

`require_post`:

```py

@require_post
def accounts_register(request: HttpRequest) -> HttpResponse:
```

This decorator ensures that the request was a POST--here, we're
checking that the registration submission page is requested with a
post, and inside the function, we'll check the form data. If you
request this page with GET, you'll get a HTTP 405 METHOD NOT ALLOWED
error.

`zulip_login_required`:

This decorator verifies that the browser is logged in (i.e. has a
valid session cookie) before providing the view for this route, or
redirects the browser to a login page. This is used in the root path
(`/`) of the website for the web client. If a request comes from a
browser without a valid session cookie, they are redirected to a login
page. It is a small fork of Django's
[login_required][login-required-link], adding a few extra checks
specific to Zulip.

```py
@zulip_login_required
def home(request: HttpRequest) -> HttpResponse:
```

[login-required-link]: https://docs.djangoproject.com/en/3.2/topics/auth/default/#django.contrib.auth.decorators.login_required

### Writing a template

Templates for the main website are found in
[templates/zerver/app](https://github.com/zulip/zulip/tree/main/templates/zerver/app).

## Writing API REST endpoints

These are code-parsable views that take x-www-form-urlencoded or JSON
request bodies, and return JSON-string responses. Almost all Zulip
view code is in the implementations of API REST endpoints.

The REST API does authentication of the user through `rest_dispatch`,
which is documented in detail at
[zerver/lib/rest.py](https://github.com/zulip/zulip/blob/main/zerver/lib/rest.py).
This method will authenticate the user either through a session token
from a cookie on the browser, or from a base64 encoded `email:api-key`
string given via HTTP basic auth for API clients.

```py
>>> import requests
>>> r = requests.get('https://api.github.com/user', auth=('hello@example.com', '0123456789abcdeFGHIJKLmnopQRSTUV'))
>>> r.status_code
-> 200
```

### Request variables

Most API views will have some arguments that are passed as part of the
request to control the behavior of the view. In any well-engineered
view, you need to write code to parse and validate that the arguments
exist and have the correct form. For many applications, this leads to
one of several bad outcomes:

- The code isn't written, so arguments aren't validated, leading to
  bugs and confusing error messages for users of the API.
- Every function starts with a long list of semi-redundant validation
  code, usually with highly inconsistent error messages.
- Every view function comes with another function that does the
  validation that has the problems from the last bullet point.

In Zulip, we solve this problem with a special decorator called
`has_request_variables` which allows a developer to declare the
arguments a view function takes and validate their types all within
the `def` line of the function. We like this framework because we
have found it makes the validation code compact, readable, and
conveniently located in the same place as the method it is validating
arguments for.

Here's an example:

```py
from zerver.decorator import require_realm_admin
from zerver.lib.request import has_request_variables, REQ

@require_realm_admin
@has_request_variables
def create_user_backend(request, user_profile, email=REQ(), password=REQ(),
                        full_name=REQ()):
    # ... code here
```

You will notice the special `REQ()` in the keyword arguments to
`create_user_backend`. `has_request_variables` parses the declared
keyword arguments of the decorated function, and for each that has an
instance of `REQ` as the default value, it extracts the HTTP parameter
with that name from the request, parses it as JSON, and passes it to
the function. It will return an nicely JSON formatted HTTP 400 error
in the event that an argument is missing, doesn't parse as JSON, or
otherwise is invalid.

`require_realm_admin` is another decorator which checks the
authorization of the given `user_profile` to make sure it belongs to a
realm administrator (and thus has permission to create a user); we
show it here primarily to show how `has_request_variables` should be
the inner decorator.

The implementation of `has_request_variables` is documented in detail
in
[zerver/lib/request.py](https://github.com/zulip/zulip/blob/main/zerver/lib/request.py))

REQ also helps us with request variable validation. For example:

- `msg_ids = REQ(json_validator=check_list(check_int))` will check
  that the `msg_ids` HTTP parameter is a list of integers, marshalled
  as JSON, and pass it into the function as the `msg_ids` Python
  keyword argument.

- `streams_raw = REQ("subscriptions", json_validator=check_list(check_string))`
  will check that the "subscriptions" HTTP parameter is a list of
  strings, marshalled as JSON, and pass it into the function with the
  Python keyword argument `streams_raw`.

- `message_id=REQ(converter=to_non_negative_int)` will check that the
  `message_id` HTTP parameter is a string containing a non-negative
  integer (`converter` differs from `json_validator` in that it does
  not automatically marshall the input from JSON).

- Since there is no need to JSON-encode strings, usually simply
  `my_string=REQ()` is correct. One can pass e.g.
  `str_validator=check_string_in(...)` where one wants to run a
  validator on the value of a string.

See
[zerver/lib/validator.py](https://github.com/zulip/zulip/blob/main/zerver/lib/validator.py)
for more validators and their documentation.

### Deciding which HTTP verb to use

When writing a new API view, you should writing a view to do just one
type of thing. Usually that's either a read or write operation.

If you're reading data, GET is the best option. Other read-only verbs
are HEAD, which should be used for testing if a resource is available to
be read with GET, without the expense of the full GET. OPTIONS is also
read-only, and used by clients to determine which HTTP verbs are
available for a given path. This isn't something you need to write, as
it happens automatically in the implementation of `rest_dispatch`--see
[zerver/lib/rest.py](https://github.com/zulip/zulip/blob/main/zerver/lib/rest.py)
for more.

If you're creating new data, try to figure out if the thing you are
creating is uniquely identifiable. For example, if you're creating a
user, there's only one user per email. If you can find a unique ID,
you should use PUT for the view. If you want to create the data multiple
times for multiple requests (for example, requesting the send_message
view multiple times with the same content should send multiple
messages), you should use POST.

If you're updating existing data, use PATCH.

If you're removing data, use DELETE.

### Idempotency

When writing a new API endpoint, with the exception of things like
sending messages, requests should be safe to repeat, without impacting
the state of the server. This is _idempotency_.

You will often want to return an error if a request to change
something would do nothing because the state is already as desired, to
make debugging Zulip clients easier. This means that the response for
repeated requests may not be the same, but the repeated requests won't
change the server more than once or cause unwanted side effects.

### Making changes to the database

If the view does any modification to the database, that change is done
in a helper function in `zerver/actions/*.py`. Those functions are
responsible for doing a complete update to the state of the server,
which often entails both updating the database and sending any events
to notify clients about the state change. When possible, we prefer to
design a clean boundary between the view function and the actions
function is such that all user input validation happens in the view
code (i.e. all 400 type errors are thrown there), and the actions code
is responsible for atomically executing the change (this is usually
signalled by having the actions function have a name starting with
`do_`. So in most cases, errors in an actions function will be the
result of an operational problem (e.g. lost connection to the
database) and lead to a 500 error. If an actions function is
responsible for validation as well, it should have a name starting
with `check_`.

For example, in [zerver/views/realm.py](https://github.com/zulip/zulip/blob/main/zerver/views/realm.py):

```py
@require_realm_admin
@has_request_variables
def update_realm(
    request: HttpRequest, user_profile: UserProfile,
    name: Optional[str]=REQ(str_validator=check_string, default=None),
    # ...
):
    realm = user_profile.realm
    # ...
            do_set_realm_property(realm, k, v, acting_user=user_profile)
    # ...
```

`realm.save()` actually saves the changes to the realm to the
database, and `send_event` sends the event to active clients belonging
to the provided list of users (in this case, all active users in the
Zulip realm).

### Calling from the web application

You should always use `channel.<method>` to make an `HTTP <method>` call
to the Zulip JSON API. As an example, in
[web/src/admin.js](https://github.com/zulip/zulip/blob/main/web/src/admin.js)

```js
var url = "/json/realm";
var data = {
    name: JSON.stringify(new_name),
}
channel.patch({
    url: url,
    data: data,
    success: function (response_data) {
        if (response_data.name !== undefined) {
            ui_report.success($t({defaultMessage: "Name changed!"}), name_status);
        }
        ...
```

### Calling from an API client

Here's how you might manually make a call from python:

```py
payload = {'name': new_name}

# email and API key
api_auth = ('hello@example.com', '0123456789abcdeFGHIJKLmnopQRSTUV')

r = requests.patch(SERVER_URL + 'api/v1/realm',
                   data=json.dumps(payload),
                   auth=api_auth,
                  )
```

This is simply an illustration; we recommend making use of the [Zulip
Python API bindings](https://www.zulipchat.com/api) since they provide
a nice interface for accessing the API.

## Legacy endpoints used by the web client

New features should conform the REST API style. The legacy, web-only
endpoints can't effectively enforce usage of a browser, so they aren't
preferable from a security perspective, and it is generally a good idea
to make your feature available to other clients, especially the mobile
clients.

These endpoints make use the older authentication decorator
`authenticated_json_view`, so you may see it in the code.

## Incoming webhook integrations

Incoming webhooks are called by other services, often to send a message as part
of those services' integrations. They are most often POST requests, and
often there is very little you can customize about them. Usually you can
expect that the webhook for a service will allow specification for the
target server for the webhook, and an API key.

If the webhook does not have an option to provide a bot email, use the
`webhook_view` decorator, to fill in the `user_profile` and
`request.client` fields of a request:

```py
@webhook_view('PagerDuty')
@has_request_variables
def api_pagerduty_webhook(request, user_profile,
                          payload=REQ(argument_type='body'),
                          stream=REQ(default='pagerduty'),
                          topic=REQ(default=None)):
```

`request.client` will be the result of `get_client("ZulipPagerDutyWebhook")`
in this example and it will be passed to `check_send_stream_message`. For
more information, see [Clients in Zulip](../subsystems/client.md).
