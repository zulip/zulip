# HTML templates

### Behavior

* Templates are automatically recompiled in development when the file
is saved; a refresh of the page should be enough to display the latest
version. You might need to do a hard refresh, as some browsers cache
webpages.

* Variables can be used in templates. The variables available to the
template are called the **context**. Passing the context to the HTML
template sets the values of those variables to the value they were
given in the context. The sections below contain specifics on how the
context is defined and where it can be found.

## Backend

For text generated in the backend, including logged-out ("portico")
pages and the webapp's base content, we use the [Jinja2][] template
engine (files in `templates/zerver`).

The syntax for using conditionals and other common structures can be
found [here][jconditionals].

The context for Jinja2 templates is assembled from a few places:

* `zulip_default_context` in `zerver/context_processors.py`.  This is
the default context available to all Jinja2 templates.

* As an argument in the `render` call in the relevant function that
renders the template. For example, if you want to find the context
passed to `index.html`, you can do:

```
$ git grep zerver/index.html '*.py'
zerver/views/home.py:    response = render(request, 'zerver/index.html',
```

The next line in the code being the context definition.

* `zproject/urls.py` for some fairly static pages that are rendered
using `TemplateView`, for example:

```
url(r'^config-error/google$', TemplateView.as_view(
    template_name='zerver/config_error.html',),
    {'google_error': True},),
```

## Frontend

For text generated in the frontend, live-rendering HTML from
JavaScript for things like the main message feed, we use the
[Handlebars][] template engine (files in `static/templates/`) and
sometimes work directly from JavaScript code (though as a policy
matter, we try to avoid generating HTML directly in JavaScript
wherever possible).

The syntax for using conditionals and other common structures can be
found [here][hconditionals].

There's no equivalent of `zulip_default_context` for the Handlebars
templates.

In order to find the context definition, you should grep without using
the file extension. For example, to find where
`invite_subscription.handlebars` is rendered, you should run something
like this:

```
$ git grep "render('invite_subscription" 'static/js'
frontend_tests/node_tests/templates.js:    var html = render('invite_subscription', args);
static/js/invite.js:    $('#streams_to_add').html(templates.render('invite_subscription', {streams: streams}));
```

The second argument to `templates.render` is the context.

### Translation

All user-facing strings (excluding pages only visible to sysadmins or
developers) should be tagged for [translation][].

[Jinja2]: http://jinja.pocoo.org/
[Handlebars]: http://handlebarsjs.com/
[trans]: http://jinja.pocoo.org/docs/dev/templates/#i18n
[i18next]: https://www.i18next.com
[official]: https://www.i18next.com/plurals.html
[helpers]: http://handlebarsjs.com/block_helpers.html
[jconditionals]: http://jinja.pocoo.org/docs/2.9/templates/#list-of-control-structures
[hconditionals]: http://handlebarsjs.com/block_helpers.html
[translation]: ../translating/translating.html
