# Provisioning and third-party dependencies

Zulip is a large project, with well over 100 third-party dependencies,
and managing them well is essential to the quality of the project.  In
this document, we discuss the various classes of dependencies that
Zulip has, and how we manage them.  Zulip's dependency management has
some really nice properties:

* **Fast provisioning**.  When switching to a different commit in the
  Zulip project with the same dependencies, it takes under 10 seconds
  to re-provision a working Zulip development environment after
  switching.  If there are new dependencies, one only needs to wait to
  download the new ones, not all the pre-existing dependencies.
* **Consistent provisioning**.  Every time a Zulip development or
  production environment is provisioned/installed, it should end up
  using the exactly correct versions of all major dependencies.
* **Low maintenance burden**.  To the extent possible, we want to
  avoid manual work and keeping track of things that could be
  automated.  This makes it easy to keep running the latest versions
  of our various dependencies.

The purpose of this document is to detail all of Zulip's third-party
dependencies and how we manage their versions.

## Provisioning

We refer to "provisioning" as the process of installing and
configuring the dependencies of a Zulip development environment.  It's
done using `tools/provision`, and the output is conveniently logged by
`var/log/provision.log` to help with debugging.  Provisioning makes
use of a lot of caching.  Some of those caches are not immune to being
corrupted if you mess around with files in your repository a lot.  We
have `tools/provision --force` to (still fairly quickly) rerun most
steps that would otherwise have been skipped due to caching.

In the Vagrant development environment, `vagrant provision` will run
the provision script; `vagrant up` will boot the machine, and will
also run an initial provision the first time only.

## Philosophy on adding third-party dependencies

In the Zulip project, we take a pragmatic approach to third-party
dependencies.  Overall, if a third-party project does something well
that Zulip needs to do (and has an appropriate license), we'd love to
use it rather than reinventing the wheel.  If the third-party project
needs some small changes to work, we prefer to make those changes and
contribute them upstream.  When the upstream maintainer is slow to
respond, we may use a fork of the dependency until the code is merged
upstream; as a result, we usually have a few packages in
`requirements.txt` that are installed from a GitHub URL.

What we look for in choosing dependencies is whether the project is
well-maintained.  Usually one can tell fairly quickly from looking at
a project's issue tracker how well-managed it is: a quick look at how
the issue tracker is managed (or not) and the test suite is usually
enough to decide if a project is going to be a high-maintenance
dependency or not.  That said, we do still take on some smaller
dependencies that don't have a well-managed project, if we feel that
using the project will still be a better investment than writing our
own implementation of that project's functionality.  We've adopted a
few projects in the past that had a good codebase but whose maintainer
no longer had time for them.

One case where we apply added scrutiny to third-party dependencies is
JS libraries.  They are a particularly important concern because we
want to keep the Zulip webapp's JS bundle small, so that Zulip
continues to load quickly on systems with low network bandwidth.
We'll look at large JS libraries with much greater scrutiny for
whether their functionality justifies their size than Python
dependencies, since an extra 50KB of code usually doesn't matter in
the backend, but does in JavaScript.

## System packages

For the third-party services like Postgres, Redis, Nginx, and RabbitMQ
that are documented in the
[architecture overview](architecture-overview.html), we rely on the
versions of those packages provided alongside the Linux distribution
on which Zulip is deployed.  Because Zulip
[only supports Ubuntu in production](prod-requirements.html), this
usually means `apt`, though we do support
[other platforms in development](dev-setup-non-vagrant.html).  Since
we don't control the versions of these dependencies, we avoid relying
on specific versions of these packages wherever possible.

The exact lists of `apt` packages needed by Zulip are maintained in a
few places:
* For production, in our puppet configuration, `puppet/zulip/`, using
  the `Package` and `SafePackage` directives.
* For development, in `APT_DEPENDENCIES` in `tools/lib/provision.py`.
* The packages needed to build a Zulip virtualenv, in
  `VENV_DEPENDENCIES` in `scripts/lib/setup_venv.py`.  These are
  separate from the rest because (1) we may need to install a
  virtualenv before running the more complex scripts that, in turn,
  install other dependencies, and (2) because that list is shared
  between development and production.

We maintain a [PPA (personal package archive)][ppa] with some packages
unique to Zulip (e.g the `tsearch_extras` postgres extension) and
backported versions of other dependencies (e.g. `camo`, to fix a buggy
`init` script).  Our goal is to shrink or eliminate this PPA where
possible by getting issues addressed in the upstream distributions.

We also rely on the `pgroonga` PPA for the `pgroonga` postgres
extension, used by our [full-text search](full-text-search.html).

## Python packages

We manage Python packages via the Python-standard `requirements.txt`
system and virtualenvs, but there’s a number of interesting details
about how Zulip makes this system work well for us that are worth
highlighting.  The system is largely managed by the code in
`scripts/lib/setup_venv.py`

* **Using `pip` to manage dependencies**.  This is standard in the
  Python ecosystem, and means we only need to record a list of
  versions in a `requirements.txt` file to declare what we're using.
  Since we have a few different installation targets, we maintain
  several `requirements.txt` format files in the `requirements/`
  directory (e.g. `dev.txt` for development, `prod.txt` for
  production, `docs.txt` for ReadTheDocs, `common.txt` for the vast
  majority of packages common to prod and development, etc.).  We use
  `pip install --no-deps` to ensure we only install the packages we
  explicitly declare as dependencies.
* **virtualenv with pinned versions**.  For a large application like
  Zulip, it is important to ensure that we're always using consistent,
  predictable versions of all of our Python dependencies.  To ensure
  this, we install our dependencies in a [virtualenv][] that contains
  only the packages and versions that Zulip needs, and we always pin
  exact versions of our dependencies in our `requirements.txt` files.
  We pin exact versions, not minimum versions, so that installing
  Zulip won't break if a dependency makes a buggy release.  A side
  effect is that it's easy to debug problems caused by dependency
  upgrades, since we're always doing those upgrades with an explicit
  commit updating the `requirements/` directory.
* **Caching of virtualenvs and packages**.  To make updating the
  dependencies of a Zulip installation efficient, we maintain a cache
  of virtualenvs named by the hash of the relevant `requirements.txt`
  file (`scripts/lib/hash_reqs.py`).  These caches live under
  `/srv/zulip-venv-cache/<hash>`.  That way, when re-provisioning a
  development environment or deploying a new production version with
  the same Python dependencies, no downloading or installation is
  required: we just use the same virtualenv.  When the only changes
  are upgraded versions, we'll use [virtualenv-clone][] to clone the
  most similar existing virtualenv and then just upgrade the packages
  needed, making small version upgrades extremely efficient.  And
  finally, we use `pip`'s built-in caching to ensure that a specific
  version of a specific package is only downloaded once.
* **Garbage-collecting caches**.  We have a tool,
  `scripts/lib/clean-venv-cache`, which will clean old cached
  virtualenvs that are no longer in use.  In production, the algorithm
  preserves recent virtualenvs as well as those in use by any current
  production deployment directory under `/home/zulip/deployments/`.
  This helps ensure that a Zulip installation doesn't leak large
  amounts of disk over time.
* **Pinning versions of indirect dependencies**.  We "pin" or "lock"
  the versions of our indirect dependencies files with
  `tools/update-locked-requirements` (powered by `pip-compile`).  What
  this means is that we have some "source" requirements files, like
  `requirements/common.txt`, that declare the packages that Zulip
  depends on directly.  Those packages have their own recursive
  dependencies.  When adding or removing a dependency from Zulip, one
  simply edits the appropriate "source" requirements files, and then
  runs `tools/update-locked-requirements`.  That tool will use `pip
  compile` to generate the `prod_lock.txt` and `dev_lock.txt` files
  that explicitly declare versions of all of Zulip's recursive
  dependencies.  For indirect dependencies (i.e. dependencies not
  explicitly declared in the source requirements files), it provides
  helpful comments explaining which direct dependency (or
  dependencies) needed that indirect dependency.  The process for
  using this system is documented in more detail in
  `requirements/README.md`.
* **Scripts**.  Often, we want a script running in production to use
  the Zulip virtualenv.  To make that work without a lot of duplicated
  code, we have a helpful library,
  `scripts/lib/setup_path_on_import.py`, which on import will put the
  currently running Python script into the Zulip virtualenv.  This is
  called by `./manage.py` to ensure that our Django code always uses
  the correct virtualenv as well.

## JavaScript and other frontend packages

We use the same set of strategies described for Python dependencies
for most of our JavaScript dependencies, so we won't repeat the
reasoning here.

* In a fashion very analogous to the Python codebase,
  `scripts/lib/node_cache.py` manages cached `node_modules`
  directories in `/srv/zulip-npm-cache`.  Each is named by its hash,
  computed by the `generate_sha1sum_node_modules` function.
  `scripts/lib/clean-npm-cache` handles garbage-collection.
* We use [yarn][], a `pip`-like tool for JavaScript, to download most
  JavaScript dependencies.  Yarn talks to standard the [npm][]
  repository.  We use the standard `package.json` file to declare our
  direct dependencies, with sections for for development and
  production.  Yarn takes care of pinning the versions of indirect
  dependencies in the `yarn.lock` file; `yarn upgrade` updates the
  `yarn.lock` files.
* `tools/update-prod-static`.  This process is discussed in detail in
  the [static asset pipeline](front-end-build-process.html) article,
  but we don't use the `node_modules` directories directly in
  production.  Instead, static assets are compiled using our static
  asset pipeline and it is the compiled assets that are served
  directly to users.  As a result, we don't ship the `node_modules`
  directory in a Zulip production release tarball, which is a good
  thing, because doing so would more than double the size of a Zulip
  release tarball.
* **Checked-in packages**.  In contrast with Python, we have a few
  JavaScript dependencies that we have copied into the main Zulip
  repository under `static/third`, often with patches.  These date
  from an era before `npm` existed.  It is a project goal to eliminate
  these checked-in versions of dependencies and instead use versions
  managed by the npm repositories.

## Node and Yarn

These are installed by `scripts/lib/install-node` (which in turn uses
the standard third-party `nvm` installer to download `node` and pin
its version) and `scripts/lib/third/install-yarn.sh` (the standard
installer for `yarn`, modified to support installing to a path that is
not the current user's home directory).

* `nvm` has its own system for installing each version of `node` at
its own path, which we use, though we install a `/usr/local/bin/node`
wrapper to access the desired version conveniently and efficiently
(`nvm` has a lot of startup overhead).
* `install-yarn.sh` is configured to install `yarn` at
`/srv/zulip-yarn`.  We don't do anything special to try to manage
multiple versions of `yarn`.

## Other third-party and generated files

In this section, we discuss the other third-party dependencies,
generated code, and other files whose original primary source is not
the Zulip server repository, and how we provision and otherwise
maintain them.

### Emoji

Zulip uses the [iamcal emoji data package][iamcal] for its emoji data
and sprite sheets.  We download this dependency using `npm`, and then
have a tool, `tools/setup/build_emoji`, which reformats the emoji data
into the files under `static/generated/emoji`.  Those files are in
turn used by our [markdown processor](markdown.html) and
`tools/update-prod-static` to make Zulip's emoji work in the various
environments where they need to be displayed.

Since processing emoji is a relatively expensive operation, as part of
optimizing provisioning, we use the same caching strategy for the
compiled emoji data as we use for virtualenvs and `node_modules`
directories, with `scripts/lib/clean-emoji-cache` responsible for
garbage-collection.  This caching and garbage-collection is required
because a correct emoji implementation involves over 1000 small image
files and a few large ones.  There is a more extended article on our
[emoji infrastructure](emoji.html).

### Translations data

Zulip's [translations infrastructure](translating.html) generates
several files from the source data, which we manage similar to our
emoji, but without the caching (and thus without the
garbage-collection).  New translations data is downloaded from
Transifex and then compiled to generate both the production locale
files and also language data in `static/locale/language*.json` using
`manage.py compilemessages`, which extends the default Django
implementation of that tool.

### Pygments data

The list of languages supported by our markdown syntax highlighting
comes from the [pygments][] package.  `tools/setup/build_pygments_data.py` is
responsible for generating `static/generated/pygments_data.js` so that
our JavaScript markdown processor has access to the supported list.

### Authors data

Zulip maintains data on the developers who have contributed the most to
the current version of Zulip in the /about page.  These data are
fetched using the GitHub API with `tools/update-authors-json`.  In
development, it just returns some basic test data to avoid adding load
to GitHub's APIs unnecessarily; it's primarily run as part of building
a release tarball.

## Modifying provisioning

When making changes to Zulip's provisioning process or dependencies,
usually one needs to think about making changes in 3 places:

* `tools/lib/provision.py`.  This is the main provisioning script,
  used by most developers to maintain their development environment.
* `docs/dev-setup-non-vagrant.md`.  This is our "manual installation"
  documentation.  Strategically, we'd like to move the support for more
  versions of Linux from here into `tools/lib/provision.py`.
* Production.  Our tools for compiling/generating static assets need
  to be called from `tools/update-prod-static`, which is called by
  `tools/build-release-tarball` (for doing Zulip releases) as well as
  `tools/upgrade-zulip-from-git` (for deploying a Zulip server off of
  master).

[virtualenv]: https://virtualenv.pypa.io/en/stable/
[virtualenv-clone]: https://github.com/edwardgeorge/virtualenv-clone/
[yarn]: https://yarnpkg.com/
[ppa]: https://launchpad.net/~tabbott/+archive/ubuntu/zulip
[iamcal]: https://github.com/iamcal/emoji-data
[pygments]: http://pygments.org/
