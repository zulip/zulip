# Life of a request

It can sometimes be confusing to figure out how to write a new feature,
or debug an existing one. Let us try to follow a request through the
Zulip codebase, and dive deep into how each part works.

We will use as our example the creation of users through the API, but we
will also highlight how alternative requests are handled.

## A request is sent to the server, and handled by [nginx](https://nginx.org/en/docs/)

When Zulip is deployed in production, all requests go through nginx.
For the most part we don't need to know how this works, except for when
it isn't working. nginx does the first level of routing--deciding which
application will serve the request (or deciding to serve the request
itself for static content).

In development, `tools/run-dev` fills the role of nginx. Static files
are in your Git checkout under `static`, and are served unminified.

## Static files are [served directly][served-directly] by nginx

[served-directly]: https://github.com/zulip/zulip/blob/main/puppet/zulip/files/nginx/zulip-include-frontend/app

Static files include JavaScript, CSS, and static assets (like emoji, avatars).

File not found errors (404) are served using a Django URL, so that we
can use configuration variables (like whether the user is logged in)
in the 404 error page.

```nginx
location /static/ {
    alias /home/zulip/prod-static/;
    # Set a nonexistent path, so we just serve the nice Django 404 page.
    error_page 404 /django_static_404.html;
}
```

## nginx routes other requests [between Django and Tornado][tornado-django]

[tornado-django]: ../overview/architecture-overview.md#django-and-tornado

All our connected clients hold open long-polling connections so that
they can receive events (messages, presence notifications, and so on) in
real-time. Events are served by Zulip's `tornado` application.

Nearly every other kind of request is served by the `zerver` Django
application.

[Here is the relevant nginx routing configuration.][nginx-config-link]

[nginx-config-link]: https://github.com/zulip/zulip/blob/main/puppet/zulip/files/nginx/zulip-include-frontend/app

## Django routes the request to a view in urls.py files

There are various
[urls.py](https://docs.djangoproject.com/en/3.2/topics/http/urls/)
files throughout the server codebase, which are covered in more detail
in
[the directory structure doc](../overview/directory-structure.md).

The main Zulip Django app is `zerver`. The routes are found in
`zproject/urls.py` and `zproject/legacy_urls.py`.

There are HTML-serving, REST API, legacy, and webhook url patterns. We
will look at how each of these types of requests are handled, and focus
on how the REST API handles our user creation example.

## Views serving HTML are internationalized by server path

If we look in
[zproject/urls.py](https://github.com/zulip/zulip/blob/main/zproject/urls.py),
we can see something called `i18n_urls`. These urls show up in the
address bar of the browser, and serve HTML.

For example, the `/features` page (preview
[here](https://zulip.com/features/)) gets translated in Chinese at
`zh-hans/features/` (preview
[here](https://zulip.com/zh-hans/features/)).

Note the `zh-hans` prefix--that url pattern gets added by `i18n_patterns`.

## API endpoints use [REST](https://www.ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm)

Our example is a REST API endpoint. It's a PUT to `/users`.

With the exception of incoming webhooks (which we do not usually control the
format of), legacy endpoints, and logged-out endpoints, Zulip uses REST
for its API. This means that we use:

- POST for creating something new where we don't have a unique
  ID. Also used as a catch-all if no other verb is appropriate.
- PUT for creating something for which we have a unique ID.
- DELETE for deleting something
- PATCH for updating or editing attributes of something.
- GET to get something (read-only)
- HEAD to check the existence of something to GET, without getting it;
  useful to check a link without downloading a potentially large link
- OPTIONS (handled automatically, see more below)

Of these, PUT, DELETE, HEAD, OPTIONS, and GET are _idempotent_, which
means that we can send the request multiple times and get the same
state on the server. You might get a different response after the first
request, as we like to give our clients an error so they know that no
new change was made by the extra requests.

POST is not idempotent--if I send a message multiple times, Zulip will
show my message multiple times. PATCH is special--it can be
idempotent, and we like to write API endpoints in an idempotent fashion,
as much as possible.

This [cookbook](http://restcookbook.com/) and
[tutorial](https://www.restapitutorial.com/) can be helpful if you are
new to REST web applications.

### PUT is only for creating new things

If you're used to using PUT to update or modify resources, you might
find our convention a little strange.

We use PUT to create resources with unique identifiers, POST to create
resources without unique identifiers (like sending a message with the
same content multiple times), and PATCH to modify resources.

In our example, `create_user_backend` uses PUT, because there's a unique
identifier, the user's email.

### OPTIONS

The OPTIONS method will yield the allowed methods.

This request:
`OPTIONS https://chat.zulip.org/api/v1/users`
yields a response with this HTTP header:
`Allow: PUT, GET`

We can see this reflected in [zproject/urls.py](https://github.com/zulip/zulip/blob/main/zproject/urls.py):

```python
rest_path('users',
          GET=get_members_backend,
          PUT=create_user_backend),
```

In this way, the API is partially self-documenting.

### Legacy endpoints are used by the web client

The endpoints from the legacy JSON API are written without REST in
mind. They are used extensively by the web client, and use POST.

You can see them in
[zproject/legacy_urls.py](https://github.com/zulip/zulip/blob/main/zproject/legacy_urls.py).

### Incoming webhook integrations may not be RESTful

Zulip endpoints that are called by other services for integrations have
to conform to the service's request format. They are likely to use
only POST.

## Django calls rest_dispatch for REST endpoints, and authenticates

For requests that correspond to a REST url pattern, Zulip configures
its url patterns (see
[zerver/lib/rest.py](https://github.com/zulip/zulip/blob/main/zerver/lib/rest.py))
so that the action called is `rest_dispatch`. This method will
authenticate the user, either through a session token from a cookie,
or from an `email:api-key` string given via HTTP basic auth for API
clients.

It will then look up what HTTP verb was used (GET, POST, etc) to make
the request, and then figure out which view to show from that.

In our example,

```python
GET=get_members_backend,
PUT=create_user_backend
```

are supplied as arguments to `rest_path`, along with the
[HTTPRequest](https://docs.djangoproject.com/en/3.2/ref/request-response/).
The request has the HTTP verb `PUT`, which `rest_dispatch` can use to
find the correct view to show:
`zerver.views.users.create_user_backend`.

## The view will authorize the user, extract request variables, and validate them

This is covered in good detail in the [writing views doc](writing-views.md).

## Results are given as JSON

Our API works on JSON requests and responses. Every API endpoint should
`raise JsonableError` in the case of an error, which gives a JSON string:

```json
{"result": "error", "msg": "<some error message>", "code": "BAD_REQUEST"}
```

in a [Django HttpResponse
object](https://docs.djangoproject.com/en/3.2/ref/request-response/)
with a `Content-Type` of 'application/json'.

To pass back data from the server to the calling client, in the event of
a successfully handled request, we use `json_success(request, data)`.

The `request` argument is a [Django HttpRequest
object](https://docs.djangoproject.com/en/3.2/ref/request-response/).
The `data` argument is a Python object which can be converted to a JSON
string and has a default value of an empty Python dictionary.

Zulip stores additional metadata it has associated with that HTTP
request in a `RequestNotes` object, which is primarily accessed in
common code used in all requests (middleware, logging, rate limiting,
etc.).

This will result in a JSON string:

```json
{"result": "success", "msg": "", "data": {"var_name1": "var_value1", "var_name2": "var_value2"}}
```

with a HTTP 200 status and a `Content-Type` of 'application/json'.

That's it!
