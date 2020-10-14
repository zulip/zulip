# HTML and CSS

## Zulip CSS organization

The Zulip application's CSS can be found in the `static/styles/`
directory.  Zulip uses [Bootstrap](https://getbootstrap.com/) as its
main third-party CSS library.

Zulip uses PostCSS for its CSS files.  There are two high-level sections
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

## CSS style guidelines

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
path('config-error/google', TemplateView.as_view(
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

## Static asset pipeline

This section documents additional information that may be useful when
developing new features for Zulip that require front-end changes,
especially those that involve adding new files. For a more general
overview, see the [new feature tutorial](../tutorials/new-feature-tutorial.md).

Our [dependencies documentation](../subsystems/dependencies.md) has useful
relevant background as well.

### Primary build process

Zulip's frontend is primarily JavaScript in the `static/js` directory;
we are working on migrating these to TypeScript modules.  Stylesheets
are written in CSS extended by various PostCSS plugins; they
are converted from plain CSS, and we have yet to take full advantage of
the features PostCSS offers.  We use Webpack to transpile and build JS
and CSS bundles that the browser can understand, one for each entry
points specified in `tools/webpack.assets.json`; source maps are
generated in the process for better debugging experience.

In development mode, bundles are built and served on the fly using
webpack-dev-server with live reloading. In production mode (and when creating a
release tarball using `tools/build-release-tarball`), the
`tools/update-prod-static` tool (called by both `tools/build-release-tarball`
and `tools/upgrade-zulip-from-git`) is responsible for orchestrating the
webpack build, JS minification and a host of other steps for getting the assets
ready for deployment.

You can trace which source files are included in which HTML templates
by comparing the `render_entrypoint` calls in the HTML templates under
`templates/` with the bundles declared in `tools/webpack.assets.json`.

### Adding static files

To add a static file to the app (JavaScript, TypeScript, CSS, images, etc),
first add it to the appropriate place under `static/`.

- Third-party packages from the NPM repository should be added to
  `package.json` for management by yarn, this allows them to be upgraded easily
  and not bloat our codebase. Run `./tools/provision` for yarn to install the
  new packages and update its lock file. You should also update
  `PROVISION_VERSION` in `version.py` in the same commit. When adding modules
  to `package.json`, please pin specific versions of them (don't using carets
  `^`, tildes `~`, etc). We prefer fixed versions so that when the upstream
  providers release new versions with incompatible APIs, it can't break Zulip.
  We update those versions periodically to ensure we're running a recent
  version of third-party libraries.
- Third-party files that we have patched should all go in
  `static/third/`. Tag the commit with "[third]" when adding or
  modifying a third-party package.  Our goal is to the extent possible
  to eliminate patched third-party code from the project.
- Our own JavaScript and TypeScript files live under `static/js`.  Ideally,
  new modules should be written in TypeScript (details on this policy below).
- CSS files live under `static/styles`.
- Portico JavaScript ("portico" means for logged-out pages) lives under
  `static/js/portico`.
- Custom SVG graphics living under `static/assets/icons` are compiled into
  custom icon webfonts by webfont-loader according to the
  `static/assets/icons/template.hbs` template.

For your asset to be included in a development/production bundle, it
needs to be accessible from one of the entry points defined in
`tools/webpack.assets.json`.

* If you plan to only use the file within the app proper, and not on the login
  page or other standalone pages, put it in the `app` bundle by importing it
  in `static/js/bundles/app.js`.
* If it needs to be available both in the app and all
  logged-out/portico pages, import it to
  `static/js/bundles/common.js` which itself is imported to the
  `app` and `common` bundles.
* If it's just used on a single standalone page (e.g. `/stats`),
  create a new entry point in `tools/webpack.assets.json`. Use the
  `bundle` macro (defined in `templates/zerver/base.html`) in the
  relevant Jinja2 template to inject the compiled JS and CSS.

If you want to test minified files in development, look for the
`DEBUG =` line in `zproject/default_settings.py` and set it to `False`.

### How it works in production

A few useful notes are:
* Zulip installs static assets in production in
`/home/zulip/prod-static`.  When a new version is deployed, before the
server is restarted, files are copied into that directory.
* We use the VFL (Versioned File Layout) strategy, where each file in
  the codebase (e.g. `favicon.ico`) gets a new name
  (e.g. `favicon.c55d45ae8c58.ico`) that contains a hash in it.  Each
  deployment, has a manifest file
  (e.g. `/home/zulip/deployments/current/staticfiles.json`) that maps
  codebase filenames to serving filenames for that deployment.  The
  benefit of this VFL approach is that all the static files for past
  deployments can coexist, which in turn eliminates most classes of
  race condition bugs where browser windows opened just before a
  deployment can't find their static assets.  It also is necessary for
  any incremental rollout strategy where different clients get
  different versions of the site.
* Some paths for files (e.g. emoji) are stored in the
  `rendered_content` of past messages, and thus cannot be removed
  without breaking the rendering of old messages (or doing a
  mass-rerender of old messages).

### CommonJS/TypeScript modules

Webpack provides seamless interoperability between different module
systems such as CommonJS, AMD and ES6. Our JS files are written in the
CommonJS format, which specifies public functions and variables as
properties of the special `module.exports` object.  We also currently
assign said object to the global `window` variable, which is a hack
allowing us to use modules without importing them with the `require()`
statement.

New modules should ideally be written in TypeScript (though in cases
where one is moving code from an existing JavaScript module, the new
commit should just move the code, not translate it to TypeScript).

TypeScript provides more accurate information to development tools,
allowing for better refactoring, auto-completion and static
analysis. TypeScript uses an ES6-like module system.  Any declaration
can be made public by adding the `export` keyword. Consuming
variables, functions, etc exported from another module should be done
with the `import` statement as oppose to accessing them from the
global `window` scope.  Internally our TypeScript compiler is
configured to transpile TS to the ES6 module system.

Read more about these module systems here:
* [TypeScript modules](https://www.typescriptlang.org/docs/handbook/modules.html)
* [CommonJS](https://nodejs.org/api/modules.html#modules_modules)

[Jinja2]: http://jinja.pocoo.org/
[Handlebars]: https://handlebarsjs.com/
[trans]: http://jinja.pocoo.org/docs/dev/templates/#i18n
[i18next]: https://www.i18next.com
[official]: https://www.i18next.com/plurals.html
[jconditionals]: http://jinja.pocoo.org/docs/2.9/templates/#list-of-control-structures
[hconditionals]: https://handlebarsjs.com/guide/#block_helpers.html
[translation]: ../translating/translating.md
