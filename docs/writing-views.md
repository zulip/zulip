# Writing views in Zulip

## What this covers

This page documents how views work in Zulip. You may want to read the 
[new feature tutorial](https://zulip.readthedocs.io/en/latest/new-feature-tutorial.html)
or the [integration guide](https://zulip.readthedocs.io/en/latest/integration-guide.html),
and treat this as a reference.

If you have experience with Django, much of this will be familiar, but
you may want to read about how REST requests are dispatched, and how
request authentication works.

This document supplements the [new feature tutorial](https://zulip.readthedocs.io/en/latest/new-feature-tutorial.html)
and the [testing](https://zulip.readthedocs.io/en/latest/testing.html)
documentation.

## What is a view?

A view in Zulip is everything that helps implement a server endpoint.
Every path that the Zulip server supports (doesn't show a 404 page for)
is a view. The obvious ones are those you can visit in your browser,
for example [/register](https://zulip.com/register/), which shows the
registration page. These paths show up in the address bar of the
browser. There are other views that are only seen by software,
namely the API views. They are used to build the various clients that
Zulip has, namely the web client (which is also used by the desktop
client) and the mobile clients.

## Modifying urls.py

A view is anything with an entry in the appropriate urls.py, usually
`zproject/urls.py`. Zulip views either serve HTML (pages for browsers) or
JSON (data for Zulip clients on all platforms, custom bots, and
integrations).

The format of the url patterns in Django is [documented here](https://docs.djangoproject.com/en/1.8/topics/http/urls/).
We have two Zulip-specific conventions we use for internationalization and for
our REST API, respectively.

## Writing human-readable views 

If you're writing a new page for the website, make sure to add it
to `i18n_urls` in `zproject/urls.py`

```diff
     i18n_urls = [
     ...
+    url(r'^quote-of-the-day/$', TemplateView.as_view(template_name='zerver/qotd.html')),
+    url(r'^postcards/$', 'zerver.views.postcards'),
]
```

As an example, if a request comes in for spanish, language code `es`,
the server path will be something like: `es/features/`.

### Decorators used for webpage views

`require_post`:

```py

@require_post
def accounts_register(request):
    # type: (HttpRequest) -> HttpResponse
```

This decorator ensures that the requst was a POST--here, we're checking
that the registration submission page is requested with a post, and
inside the funciton we'll check the form data. If you request this page
with GET, you'll get a HTTP 405 METHOD NOT ALLOWED error.

`zulip_login_required`:

This decorator verifies that the browser is logged in before providing
the view for this route, or redirects the browser to a login page. This
is used in the root path (`/`) of the website for the web client. If a
request comes from a browser without a valid session cookie, they are
redirected to a login page.

```py
@zulip_login_required
def home(request):
    # type: (HttpRequest) -> HttpResponse
```

### Writing a template

Templates for the main website are found in [templates/zerver](https://github.com/zulip/zulip/blob/master/templates/zerver)


## Writing API REST endpoints

These are code-parseable views that take x-www-form-urlencoded or JSON
request bodies, and return JSON-string responses.

The REST API does authentication of the user through `rest_dispatch`,
which is documented in detail at [zerver/lib/rest.py](https://github.com/zulip/zulip/blob/master/zerver/lib/rest.py).
This method will authenticate the user either through a session token
from a cookie on the browser, or from a base64 encoded `email:api-key`
string given via HTTP Basic Auth for API clients.

``` py
>>> import requests
>>> r = requests.get('https://api.github.com/user', auth=('hello@example.com', '0123456789abcdeFGHIJKLmnopQRSTUV'))
>>> r.status_code
-> 200
```

### Decorators for REST API endpoints

As just mentioned, you don't need special authentication decorators for
REST API endpoints that use `rest_dispatch` as the specified view in
`urls.py`. You will need authentication decorators for the legacy API,
and for webhooks. This means that if you need to write a view that
should not require an authenticated user, you need to write a
legacy-style endpoint.

`require_realm_admin` should be used for actions which should only be
available to admins
`has_request_variables` should be used in conjunction with `REQ` keyword
arguments. See more in the next section

New pages are not typically 
from zerver.decorator import has_request_variables, REQ, JsonableError, \
    require_realm_admin
    
### Request variables

There are some special decorators we may use for a given view. Our
example uses `require_realm_admin` and `has_request_variables`:
``` py
@require_realm_admin
@has_request_variables
def create_user_backend(request, user_profile, email=REQ(), password=REQ(),
                        full_name=REQ(), short_name=REQ()):
```

`require_realm_admin` checks the authorization of the given
`user_profile` to make sure it belongs to a realm admin and thus has
permission to create a user.

We can see a special `REQ()` in the keyword arguments to `create_user_backend`.
The body of a request is expected to be in JSON format, so this is used
in conjunction with the `has_request_variables` decorator to unpack the
variables in the JSON string for use in the function. The implementation
of `has_request_variables` is documented heavily in [zerver/lib/request.py](https://github.com/zulip/zulip/blob/master/zerver/lib/request.py))

REQ also helps us with request variable validation. For example:
`msg_ids = REQ(validator=check_list(check_int))`
will check that the `msg_ids` request variable is a list of integers,
marshalled as JSON.

See [zerver/lib/validator.py](https://github.com/zulip/zulip/blob/master/zerver/lib/validator.py) for more validators and their documentation.

### Deciding which HTTP verb to use

When writing a new API view, you should limiting your view to do just
one thing. Usually that's either a read or write operation.

If you're reading data, GET is the best option. Other read-only verbs
are HEAD, which should be used for testing if a resource is available to
be read with GET, without the expense of the full GET. OPTIONS is also
read-only, and used by clients to determine which HTTP verbs are
available for a given path. This isn't something you need to write, as
it happens automatically in the implementation of `rest_dispatch`--see
[zerver/lib/rest.py](https://github.com/zulip/zulip/blob/master/zerver/lib/rest.py)
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
message sending, requests should be safe to repeat, without affecting
the state of the server. This is *idempotency*.

You will often return an error if a request was made more than once, to
make debugging Zulip clients easier. This means that the response for
repeated requests may not be the same, but the repeated requests won't
change the server more than once or cause unwanted side effects.

### Making changes to the database

If the view does any modification to the database, that change is done
in a helper function in `zerver/lib/actions.py`.

For example, in [zerver/views/__init__.py](https://github.com/zulip/zulip/blob/master/zerver/views/__init__.py):

```py
@require_realm_admin
@has_request_variables
def update_realm(request, user_profile, name=REQ(validator=check_string, default=None), ...)):
    # type: (HttpRequest, UserProfile, ...) -> HttpResponse
    realm = user_profile.realm
    data = {} # type: Dict[str, Any]
    if name is not None and realm.name != name:
        do_set_realm_name(realm, name)
        data['name'] = 'updated'
```

and in [zerver/lib/actions.py](https://github.com/zulip/zulip/blob/master/zerver/lib/actions.py):

```py
def do_set_realm_name(realm, name):
    # type: (Realm, text_type) -> None
    realm.name = name
    realm.save(update_fields=['name'])
    event = dict(
        type="realm",
        op="update",
        property='name',
        value=name,
    )
    send_event(event, active_user_ids(realm))
```

`realm.save()` actually saves the changes to the realm to the database.

### Calling from the web client

You can use channel.<method> to call to the proper view from anywhere in
the web client code. In this case, in [static/js/admin.js](https://github.com/zulip/zulip/blob/master/static/js/admin.js)

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
            ui.report_success(i18n.t("Name changed!"), name_status);
        }
        ...
```

If the user is logged in, this will handle passing in the session token
automatically.


### Calling from an API client

Here's how you might handle calling from python:

```py
payload = {'name': new_name}

# email and API key
api_auth = ('hello@example.com', '0123456789abcdeFGHIJKLmnopQRSTUV')

r = requests.patch(SERVER_URL + 'api/v1/realm',
                   data=json.dumps(payload),
                   auth=api_auth,
                  )
```

## Legacy endpoints used by the web client

New features should conform the REST API style. The legacy, web-only
endpoints can't effectively enforce usage of a browser, so they aren't
preferable from a security perspective, and it is generally a good idea
to make your feature available to other clients, especially the mobile
clients.

## Webhook integration endpoints

Webhooks are called by other services, often to send a message as part
of those services' integrations. They are most often POST requests, and
often there is very little you can customize about them. Usually you can
expect that the webhook for a service will allow specification for the
target server for the webhook, and an API key.

If the webhook does not have an option to provide a bot email, use the
`api_key_only_webhook_view` decorator, to fill in the `user_profile` and
`client` fields of a request:

``` py
@api_key_only_webhook_view('PagerDuty')
@has_request_variables
def api_pagerduty_webhook(request, user_profile, client,
                          payload=REQ(argument_type='body'),
                          stream=REQ(default='pagerduty'),
                          topic=REQ(default=None)):
```
The `client` will be the result of `get_client("ZulipPagerDutyWebhook")`
in this example.


