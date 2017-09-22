# Static asset pipeline

This page documents additional information that may be useful when
developing new features for Zulip that require front-end changes,
especially those that involve adding new files. For a more general
overview, see the [new feature tutorial](new-feature-tutorial.html).

Our [dependencies documentation](dependencies.html) has useful
relevant background as well.

## Primary build process

Most of the existing JS in Zulip is written
in [IIFE](https://www.google.com/#q=iife)-wrapped
modules, one per file in the `static/js` directory. We will over time migrate
this to Typescript modules. In development mode files are loaded using webpack
eval with sourcemaps. In production mode (and when creating a release tarball
using `tools/build-release-tarball`), JavaScript files are concatenated and
minified. We use the
[django pipeline extension](https://django-pipeline.readthedocs.io/en/latest/)
to manage our static assets, webpack, and typescript.  The main
internal tool that does all of this work is
`tools/update-prod-static`, which is called by both
`tools/build-release-tarball` and `tools/upgrade-zulip-from-git`.

## Adding static files

To add a static file to the app (JavaScript, CSS, images, etc), first
add it to the appropriate place under `static/`.

- Third-party files that we haven't patched should be installed via
  `yarn`, so that it's easy to upgrade them and third-party code
  doesn't bloat the Zulip repository.  You can then access them in
  `webpack.assets.json` via their paths under `node_modules`.
  You'll want to add these to the `package.json` in the root of the
  repository, and then provision (to have `yarn` download them) before
  continuing.  Your commit should also update `PROVISION_VERSION` in
  `version.py`.  When adding modules to `package.json`, please pin
  specific versions of them (don't using carets `^`, tildes `~`, etc).
  We prefer fixed versions so that when the upstream providers release
  new versions with incompatible APIs, it can't break Zulip.  We
  update those versions periodically to ensure we're running a recent
  version of third-party libraries.
- Third-party files that we have patched should all go in
  `static/third/`. Tag the commit with "[third]" when adding or
  modifying a third-party package.  Our goal is to the extent possible
  to eliminate patched third-party code from the project.
  - Our own JavaScript lives under `static/js`; Typescript files live under
  static/ts; CSS lives under `static/styles`. Portico JavaScript ("portico" means
  for logged-out pages) lives under `static/js/portico`.

After you add a new JavaScript file, it needs to be imported by
another file or specified in the `entries` dictionary defined in
`tools/webpack.assets.json` to be included in the concatenated file;
this will magically ensure it is available both in development and
production.  CSS should be added to the `STYLESHEETS` section of
`PIPELINE` in `zproject/settings.py`.  A few notes on doing this:

* For new files you should generally import it from another file rather
  than adding it to `tools/webpack.assets.json`
* If you plan to only use the JS/CSS within the app proper, and not on
  the login page or other standalone pages, put it in the `app`
  bundle.
* If you plan to use it in both, put it in the `common` bundle.
* If it's just used on a single standalone page (e.g. `/stats`), give
  it its own bundle.  To load a bundle in the relevant Jinja2 template
  for that page, use `render_bundle` and `stylesheet` for JS and CSS,
  respectively.
* If you modify `tools/webpack.assets.json` you will need to restart
  the server.

If you want to test minified files in development, look for the
`PIPELINE_ENABLED =` line in `zproject/settings.py` and set it to `True`
-- or just set `DEBUG = False`.

Note that `static/html/5xx.html` will only render properly if
minification is enabled, since they, by nature, hardcode the path
`static/min/portico.css`.

## How it works in production

You can learn a lot from reading about django-pipeline, but a few
useful notes are:
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

## Webpack/CommonJS/ES6/Typescript modules

New JS written for Zulip can be written
as [Typescript](http://www.typescriptlang.org/) or if a more incremental
migration is required, CommonJS modules (bundled
using [webpack](https://webpack.github.io/), though this will be taken care of
automatically whenever `run-dev.py` is running). (CommonJS is the same module
format that Node uses, so see
the [Node documentation](https://nodejs.org/docs/latest/api/modules.html) for
more information on the syntax.)

All JavaScript we provide will eventually be migrated to Typescript,
which will make refactoring the frontend code easier and allow static
analyzers to reason about our code more easily.

Declare entry points in `webpack.assets.json`. Any modules you add
will need to be imported from this file (or one of its dependencies)
in order to be included in the script bundle.

### Hot Reloading

Webpack support hot reloading. To enable it you will need to add

```
// This reloads the module in development rather than refreshing the page
if (module.hot) {
    module.hot.accept();
}

```

To the entry point of any JavaScript file you want to hot reload
rather than refeshing the page on a change.
