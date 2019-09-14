# Static asset pipeline

This page documents additional information that may be useful when
developing new features for Zulip that require front-end changes,
especially those that involve adding new files. For a more general
overview, see the [new feature tutorial](../tutorials/new-feature-tutorial.html).

Our [dependencies documentation](../subsystems/dependencies.html) has useful
relevant background as well.

## Primary build process

Most of the existing JS in Zulip is written in
[IIFE](https://www.google.com/#q=iife)-wrapped modules, one per file
in the `static/js` directory. We will over time migrate these to
Typescript modules.  Stylesheets are written in the Sass extension of
CSS (with the scss syntax), they are converted from plain CSS and we
have yet to take full advantage of the features Sass offers.  We use
Webpack to transpile and build JS and CSS bundles that the browser can
understand, one for each entry points specifed in
`tools/webpack.assets.json`; source maps are generated in the process
for better debugging experience.

In development mode, bundles are built and served on the fly using
webpack-dev-server with live reloading. In production mode (and when creating a
release tarball using `tools/build-release-tarball`), the
`tools/update-prod-static` tool (called by both `tools/build-release-tarball`
and `tools/upgrade-zulip-from-git`) is responsible for orchestrating the
webpack build, JS minification and a host of other steps for getting the assets
ready for deployment.

## Adding static files

To add a static file to the app (JavaScript, TypeScript, CSS/Sass, images, etc),
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
- CSS/Sass files lives under `static/styles`.
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
`DEBUG =` line in `zproject/settings.py` and set it to `False`.

## How it works in production

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

## CommonJS/Typescript modules

Webpack provides seemless interoperability between different module
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
global `window` scope.  Internally our typescript compiler is
configured to transpile TS to the ES6 module system.

Read more about these module systems here:
* [TypeScript modules](https://www.typescriptlang.org/docs/handbook/modules.html)
* [CommonJS](https://nodejs.org/api/modules.html#modules_modules)
