# HTML and CSS

## Zulip CSS organization

There are two high-level sections of CSS: the "portico" (logged-out
pages like `/help/`, `/login/`, etc.), and the app. The Zulip
application's CSS can be found in the `web/styles/` directory, while
the portico CSS lives under the `web/styles/portico/` subdirectory.

To generate its CSS files, Zulip uses [PostCSS](https://postcss.org/)
and a number of PostCSS plugins, including
[postcss-nesting](https://github.com/csstools/postcss-nesting#readme),
whose rules are derived from the [CSS Nesting](https://drafts.csswg.org/css-nesting-1/)
specification.

## Editing Zulip CSS

If you aren't experienced with doing web development and want to make
CSS changes, we recommend reading the excellent [Chrome developer tools
guide to the Elements panel and CSS](https://developer.chrome.com/docs/devtools/overview/#elements),
as well as the [section on viewing and editing CSS](https://developer.chrome.com/docs/devtools/css/)
to learn about all the great tools that you can use to modify and test
changes to CSS interactively in-browser (without even having the
reload the page!).

Our CSS is formatted with [Prettier](https://prettier.io/). You can
ask Prettier to reformat all code via our [linter
tool](../testing/linters.md) with `tools/lint --only=prettier --fix`.
You can also [integrate it with your
editor](https://prettier.io/docs/en/editors.html).

Zulip's development environment has hot code-reloading configured, so
changes made in source files will immediately take effect in open
browser windows, either by live-updating the CSS or reloading the
browser window (following backend changes).

## CSS style guidelines

### Avoid duplicated code

Without care, it's easy for a web application to end up with thousands
of lines of duplicated CSS code, which can make it very difficult to
understand the current styling or modify it. We would very much like
to avoid such a fate. So please make an effort to reuse existing
styling, clean up now-unused CSS, etc., to keep things maintainable.

Opt to write CSS in CSS files. Avoid using the `style=` attribute in
HTML except for styles that are set dynamically. For example, we set
the colors for specific streams (`{{stream_color}}`) on different
elements dynamically, in files like `user_stream_list_item.hbs`:

```html
<span
  class="stream-privacy-original-color-{{stream_id}} stream-privacy filter-icon"
  style="color: {{stream_color}}">
```

But for most other cases, its preferable to define logical classes and
put your styles in external CSS files such as `zulip.css` or a more
specific CSS file, if one exists. See the contents of the `web/styles/`
directory.

### Be consistent with existing similar UI

Ideally, do this by reusing existing CSS declarations, so that any
improvements we make to the styling can improve all similar UI
elements.

### Use clear, unique names for classes and object IDs

This makes it much easier to read the code and use `git grep` to find
where a particular class is used.

Don't use the tag name in a selector unless you have to. In other words,
use `.foo` instead of `span.foo`. We shouldn't have to care if the tag
type changes in the future.

Additionally, multi-word class and ID values should be hyphenated,
also known as _kebab case_. In HTML, opt for `class="my-multiword-class"`,
with its corresponding CSS selector as `.my-multiword-class`.

## Validating CSS

When changing any part of the Zulip CSS, it's important to check that
the new CSS looks good at a wide range of screen widths, from very
wide screen (e.g. 1920px) all the way down to narrow phone screens
(e.g. 480px).

For complex changes, it's definitely worth testing in a few different
browsers to make sure things look the same.

## HTML templates

### Behavior

- Templates are automatically recompiled in development when the file
  is saved; a refresh of the page should be enough to display the latest
  version. You might need to do a hard refresh, as some browsers cache
  webpages.

- Variables can be used in templates. The variables available to the
  template are called the **context**. Passing the context to the HTML
  template sets the values of those variables to the value they were
  given in the context. The sections below contain specifics on how the
  context is defined and where it can be found.

### Backend templates

For text generated in the backend, including logged-out ("portico")
pages and the web app's base content, we use the [Jinja2][] template
engine (files in `templates/zerver`).

The syntax for using conditionals and other common structures can be
found [here][jconditionals].

The context for Jinja2 templates is assembled from a few places:

- `zulip_default_context` in `zerver/context_processors.py`. This is
  the default context available to all Jinja2 templates.

- As an argument in the `render` call in the relevant function that
  renders the template. For example, if you want to find the context
  passed to `index.html`, you can do:

```console
$ git grep zerver/app/index.html '*.py'
zerver/views/home.py:    response = render(request, 'zerver/app/index.html',
```

The next line in the code being the context definition.

- `zproject/urls.py` for some fairly static pages that are rendered
  using `TemplateView`, for example:

```python
path('config-error/google', TemplateView.as_view(
    template_name='zerver/config_error.html',),
    {'google_error': True},),
```

### Frontend templates

For text generated in the frontend, live-rendering HTML from
JavaScript for things like the main message feed, we use the
[Handlebars][] template engine (files in `web/templates/`) and
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
developers) should be tagged for [translation][trans].

### Tooltips

Zulip uses [TippyJS](https://atomiks.github.io/tippyjs/) for its tooltips.

## Static asset pipeline

This section documents additional information that may be useful when
developing new features for Zulip that require front-end changes,
especially those that involve adding new files. For a more general
overview, see the [new feature tutorial](../tutorials/new-feature-tutorial.md).

Our [dependencies documentation](dependencies.md) has useful
relevant background as well.

### Primary build process

Zulip's frontend is primarily JavaScript in the `web/src` directory;
we are working on migrating these to TypeScript modules. Stylesheets
are written in CSS extended by various PostCSS plugins; they are
converted from plain CSS, and we have yet to take full advantage of
the features PostCSS offers. We use Webpack to transpile and build JS
and CSS bundles that the browser can understand, one for each entry
points specified in `web/webpack.*assets.json`; source maps are
generated in the process for better debugging experience.

In development mode, bundles are built and served on the fly using
webpack-dev-server with live reloading. In production mode (and when creating a
release tarball using `tools/build-release-tarball`), the
`tools/update-prod-static` tool (called by both `tools/build-release-tarball`
and `tools/upgrade-zulip-from-git`) is responsible for orchestrating the
webpack build, JS minification and a host of other steps for getting the assets
ready for deployment.

You can trace which source files are included in which HTML templates
by comparing the `entrypoint` variables in the HTML templates under
`templates/` with the bundles declared in `web/webpack.*assets.json`.

### Adding static files

To add a static file to the app (JavaScript, TypeScript, CSS, images, etc),
first add it to the appropriate place under `static/`.

- Third-party packages from the NPM repository should be added to
  `package.json` for management by pnpm, this allows them to be upgraded easily
  and not bloat our codebase. Run `./tools/provision` for pnpm to install the
  new packages and update its lock file. You should also update
  `PROVISION_VERSION` in `version.py` in the same commit.
- Third-party files that we have patched should all go in
  `web/third/`. Tag the commit with "[third]" when adding or
  modifying a third-party package. Our goal is to the extent possible
  to eliminate patched third-party code from the project.
- Our own JavaScript and TypeScript files live under `web/src`. Ideally,
  new modules should be written in TypeScript (details on this policy below).
- CSS files live under `web/styles`.
- Portico JavaScript ("portico" means for logged-out pages) lives under
  `web/src/portico`.
- Custom SVG graphics living under `web/images/icons` are compiled into
  custom icon webfonts by webfont-loader according to the
  `web/images/icons/template.hbs` template.

For your asset to be included in a development/production bundle, it
needs to be accessible from one of the entry points defined either in
`web/webpack.assets.json` or `web/webpack.dev-assets.json`.

- If you plan to only use the file within the app proper, and not on the login
  page or other standalone pages, put it in the `app` bundle by importing it
  in `web/src/bundles/app.ts`.
- If it needs to be available both in the app and all
  logged-out/portico pages, import it to
  `web/src/bundles/common.ts` which itself is imported to the
  `app` and `common` bundles.
- If it's just used on a single standalone page which is only used in
  a development environment (e.g. `/devlogin`) create a new entry
  point in `web/webpack.dev-assets.json` or it's used in both
  production and development (e.g. `/stats`) create a new entry point
  in `web/webpack.assets.json`. Use the `bundle` macro (defined in
  `templates/zerver/base.html`) in the relevant Jinja2 template to
  inject the compiled JS and CSS.

If you want to test minified files in development, look for the
`DEBUG =` line in `zproject/default_settings.py` and set it to `False`.

### How it works in production

A few useful notes are:

- Zulip installs static assets in production in
  `/home/zulip/prod-static`. When a new version is deployed, before the
  server is restarted, files are copied into that directory.
- We use the VFL (versioned file layout) strategy, where each file in
  the codebase (e.g. `favicon.ico`) gets a new name
  (e.g. `favicon.c55d45ae8c58.ico`) that contains a hash in it. Each
  deployment, has a manifest file
  (e.g. `/home/zulip/deployments/current/staticfiles.json`) that maps
  codebase filenames to serving filenames for that deployment. The
  benefit of this VFL approach is that all the static files for past
  deployments can coexist, which in turn eliminates most classes of
  race condition bugs where browser windows opened just before a
  deployment can't find their static assets. It also is necessary for
  any incremental rollout strategy where different clients get
  different versions of the site.
- Some paths for files (e.g. emoji) are stored in the
  `rendered_content` of past messages, and thus cannot be removed
  without breaking the rendering of old messages (or doing a
  mass-rerender of old messages).

### ES6/TypeScript modules

JavaScript modules in the frontend are [ES6
modules](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules)
that are [transpiled by
webpack](https://webpack.js.org/api/module-methods/#es6-recommended).
Any variable, function, etc. can be made public by adding the
[`export`
keyword](https://developer.mozilla.org/en-US/docs/web/javascript/reference/statements/export),
and consumed from another module using the [`import`
statement](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/import).

New modules should ideally be written in TypeScript (though in cases
where one is moving code from an existing JavaScript module, the new
commit should just move the code, not translate it to TypeScript).
TypeScript provides more accurate information to development tools,
allowing for better refactoring, auto-completion and static analysis.
TypeScript also uses the ES6 module system. See our documentation on
[TypeScript static types](../testing/typescript).

Webpack does not ordinarily allow modules to be accessed directly from
the browser console, but for debugging convenience, we have a custom
webpack plugin (`web/debug-require-webpack-plugin.ts`) that exposes
a version of the `require()` function to the development environment
browser console for this purpose. For example, you can access our
`people` module by evaluating
`people = require("./src/people")`, or the third-party `lodash`
module with `_ = require("lodash")`. This mechanism is **not** a
stable API and should not be used for any purpose other than
interactive debugging.

We have one module, `zulip_test`, that’s exposed as a global variable
using `expose-loader` for direct use in Puppeteer tests and in the
production browser console. If you need to access a variable or
function in those scenarios, add it to `zulip_test`. This is also
**not** a stable API.

[jinja2]: http://jinja.pocoo.org/
[handlebars]: https://handlebarsjs.com/
[trans]: https://jinja.palletsprojects.com/en/3.0.x/extensions/#i18n-extension
[jconditionals]: http://jinja.pocoo.org/docs/2.9/templates/#list-of-control-structures
[hconditionals]: https://handlebarsjs.com/guide/block-helpers.html#block-helpers
[translation]: ../translating/translating.md
