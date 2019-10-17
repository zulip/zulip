# HTML and CSS

## Zulip CSS organization

The Zulip application's CSS can be found in the `static/styles/`
directory.  Zulip uses [Bootstrap](http://getbootstrap.com/) as its
main third-party CSS library.

Zulip uses SCSS for its CSS files.  There are two high-level sections
of CSS: the "portico" (logged-out pages like /help/, /login/, etc.),
and the app.  The portico CSS lives under the `static/styles/portico`
subdirectory.

## Editing Zulip CSS

If you aren't experienced with doing web development and want to make
CSS changes, we recommend reading the excellent [Chrome web inspector
guide on editing HTML/CSS](https://developer.chrome.com/devtools/docs/dom-and-styles),
especially the [section on
CSS](https://developer.chrome.com/devtools/docs/dom-and-styles#styles)
to learn about all the great tools that you can use to modify and test
changes to CSS interactively in-browser (without even having the
reload the page!).

Zulip's development environment has hot code reloading configured, so
changes made in source files will immediately take effect in open
browser windows, either by live-updating the CSS or reloading the
browser window (following backend changes).

## CSS Style guidelines

### Avoid duplicated code

Without care, it's easy for a web application to end up with thousands
of lines of duplicated CSS code, which can make it very difficult to
understand the current styling or modify it.  We would very much like
to avoid such a fate.  So please make an effort to reuse existing
styling, clean up now-unused CSS, etc., to keep things maintainable.

### Be consistent with existing similar UI

Ideally, do this by reusing existing CSS declarations, so that any
improvements we make to the styling can improve all similar UI
elements.

### Use clear, unique names for classes and object IDs

This makes it much easier to read the code and use `git grep` to find
where a particular class is used.

## Validating CSS

When changing any part of the Zulip CSS, it's important to check that
the new CSS looks good at a wide range of screen widths, from very
wide screen (e.g. 1920px) all the way down to narrow phone screens
(e.g. 480px).

For complex changes, it's definitely worth testing in a few different
browsers to make sure things look the same.

## HTML templates

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

### Backend templates

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
$ git grep zerver/app/index.html '*.py'
zerver/views/home.py:    response = render(request, 'zerver/app/index.html',
```

The next line in the code being the context definition.

* `zproject/urls.py` for some fairly static pages that are rendered
using `TemplateView`, for example:

```
url(r'^config-error/google$', TemplateView.as_view(
    template_name='zerver/config_error.html',),
    {'google_error': True},),
```

### Frontend templates

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

### Toolchain

Handlebars is in our `package.json` and thus ends up in `node_modules`; We use
handlebars-loader to load and compile templates during the webpack bundling
stage. In the development environment, webpack will trigger a browser reload
whenever a template is changed.

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
[translation]: ../translating/translating.md
