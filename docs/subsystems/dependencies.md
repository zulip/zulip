# Provisioning and third-party dependencies

Zulip is a large project, with well over 100 third-party dependencies,
and managing them well is essential to the quality of the project. In
this document, we discuss the various classes of dependencies that
Zulip has, and how we manage them. Zulip's dependency management has
some really nice properties:

- **Fast provisioning**. When switching to a different commit in the
  Zulip project with the same dependencies, it takes under 5 seconds
  to re-provision a working Zulip development environment after
  switching. If there are new dependencies, one only needs to wait to
  download the new ones, not all the pre-existing dependencies.
- **Consistent provisioning**. Every time a Zulip development or
  production environment is provisioned/installed, it should end up
  using the exactly correct versions of all major dependencies.
- **Low maintenance burden**. To the extent possible, we want to
  avoid manual work and keeping track of things that could be
  automated. This makes it easy to keep running the latest versions
  of our various dependencies.

The purpose of this document is to detail all of Zulip's third-party
dependencies and how we manage their versions.

## Provisioning

We refer to "provisioning" as the process of installing and
configuring the dependencies of a Zulip development environment. It's
done using `tools/provision`, and the output is conveniently logged by
`var/log/provision.log` to help with debugging. Provisioning makes
use of a lot of caching. Some of those caches are not immune to being
corrupted if you mess around with files in your repository a lot. We
have `tools/provision --force` to (still fairly quickly) rerun most
steps that would otherwise have been skipped due to caching.

In the Vagrant development environment, `vagrant provision` will run
the provision script; `vagrant up` will boot the machine, and will
also run an initial provision the first time only.

### PROVISION_VERSION

In `version.py`, we have a special parameter, `PROVISION_VERSION`,
which is used to help ensure developers don't spend time debugging
test/linter/etc. failures that actually were caused by the developer
rebasing and forgetting to provision". `PROVISION_VERSION` has a
format of `(x, y)`; when `x` doesn't match the value from the last time
the user provisioned, or `y` is higher than the value from last
time, most Zulip tools will crash early and ask the user to provision.
This has empirically made a huge impact on how often developers spend
time debugging a "weird failure" after rebasing that had an easy
solution. (Of course, the other key part of achieving this is all the
work that goes into making sure that `provision` reliably leaves the
development environment in a good state.)

`PROVISION_VERSION` must be manually updated when making changes that
require re-running provision, so don't forget about it!

## Philosophy on adding third-party dependencies

In the Zulip project, we take a pragmatic approach to third-party
dependencies. Overall, if a third-party project does something well
that Zulip needs to do (and has an appropriate license), we'd love to
use it rather than reinventing the wheel. If the third-party project
needs some small changes to work, we prefer to make those changes and
contribute them upstream. When the upstream maintainer is slow to
respond, we may use a fork of the dependency until the code is merged
upstream; as a result, we usually have a few packages in
`requirements.txt` that are installed from a GitHub URL.

What we look for in choosing dependencies is whether the project is
well-maintained. Usually one can tell fairly quickly from looking at
a project's issue tracker how well-managed it is: a quick look at how
the issue tracker is managed (or not) and the test suite is usually
enough to decide if a project is going to be a high-maintenance
dependency or not. That said, we do still take on some smaller
dependencies that don't have a well-managed project, if we feel that
using the project will still be a better investment than writing our
own implementation of that project's functionality. We've adopted a
few projects in the past that had a good codebase but whose maintainer
no longer had time for them.

One case where we apply added scrutiny to third-party dependencies is
JS libraries. They are a particularly important concern because we
want to keep the Zulip web app's JS bundle small, so that Zulip
continues to load quickly on systems with low network bandwidth.
We'll look at large JS libraries with much greater scrutiny for
whether their functionality justifies their size than Python
dependencies, since an extra 50KB of code usually doesn't matter in
the backend, but does in JavaScript.

## System packages

For the third-party services like PostgreSQL, Redis, nginx, and RabbitMQ
that are documented in the
[architecture overview](../overview/architecture-overview.md), we rely on the
versions of those packages provided alongside the Linux distribution
on which Zulip is deployed. Because Zulip
[only supports Debian or Ubuntu in production](../production/requirements.md),
this usually means `apt`, though we do support
[other platforms in development](../development/setup-advanced.md). Since
we don't control the versions of these dependencies, we avoid relying
on specific versions of these packages wherever possible.

The exact lists of `apt` packages needed by Zulip are maintained in a
few places:

- For production, in our Puppet configuration, `puppet/zulip/`, using
  the `Package` and `SafePackage` directives.
- For development, in `SYSTEM_DEPENDENCIES` in `tools/lib/provision.py`.
- The packages needed to build a Zulip virtualenv, in
  `VENV_DEPENDENCIES` in `scripts/lib/setup_venv.py`. These are
  separate from the rest because (1) we may need to install a
  virtualenv before running the more complex scripts that, in turn,
  install other dependencies, and (2) because that list is shared
  between development and production.

We also rely on the PGroonga PPA for the PGroonga PostgreSQL
extension, used by our [full-text search](full-text-search.md).

## Python packages

Zulip uses the version of Python itself provided by the host OS for
the Zulip server. We currently support Python 3.10 and newer, with
Ubuntu 22.04 being the platform requiring 3.10 support. The comments
in `.github/workflows/zulip-ci.yml` document the Python versions used
by each supported platform.

We manage third-party Python packages using [uv](https://docs.astral.sh/uv/),
with our requirements listed in
[pyproject.toml](https://docs.astral.sh/uv/concepts/projects/layout/#the-pyprojecttoml),
and locked versions stored in
[`uv.lock`](https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile).

- **Scripts**. Often, we want a script running in production to use
  the Zulip virtualenv. To make that work without a lot of duplicated
  code, we have a helpful function,
  `scripts.lib.setup_path.setup_path`, which on import will put the
  currently running Python script into the Zulip virtualenv. This is
  called by `./manage.py` to ensure that our Django code always uses
  the correct virtualenv as well.
- **Mypy type checker**. Because we're using mypy in a strict mode,
  when you add use of a new Python dependency, you usually need to
  either adds stubs to the `stubs/` directory for the library, or edit
  `pyproject.toml` in the root of the Zulip project to configure
  `ignore_missing_imports` for the new library. See
  [our mypy docs][mypy-docs] for more details.

[mypy-docs]: ../testing/mypy.md

## JavaScript and other frontend packages

We use the same set of strategies described for Python dependencies
for most of our JavaScript dependencies, so we won't repeat the
reasoning here.

- We use [pnpm][], a `pip`-like tool for JavaScript, to download most
  JavaScript dependencies. pnpm talks to the standard [npm][]
  repository. We use the standard `package.json` file to declare our
  direct dependencies, with sections for development and
  production. pnpm takes care of pinning the versions of indirect
  dependencies in the `pnpm-lock.yaml` file; `pnpm install` updates the
  `pnpm-lock.yaml` file.
- `tools/update-prod-static`. This process is discussed in detail in
  the [static asset pipeline](html-css.md#static-asset-pipeline)
  article, but we don't use the `node_modules` directories directly in
  production. Instead, static assets are compiled using our static
  asset pipeline and it is the compiled assets that are served
  directly to users. As a result, we don't ship the `node_modules`
  directory in a Zulip production release tarball, which is a good
  thing, because doing so would more than double the size of a Zulip
  release tarball.
- **Checked-in packages**. In contrast with Python, we have a few
  JavaScript dependencies that we have copied into the main Zulip
  repository under `web/third`, often with patches. These date
  from an era before `npm` existed. It is a project goal to eliminate
  these checked-in versions of dependencies and instead use versions
  managed by the npm repositories.

## Node.js and pnpm

Node.js is installed by `scripts/lib/install-node` to
`/srv/zulip-node` and symlinked to `/usr/local/bin/node`. A pnpm
symlink at `/usr/local/bin/pnpm` is managed by
[Corepack](https://nodejs.org/api/corepack.html).

We don't do anything special to try to manage multiple versions of
Node.js. (Previous versions of Zulip installed multiple versions of
Node.js using the third-party `nvm` installer, but the current version
no longer uses `nvm`; if it’s present in `/usr/local/nvm` where
previous versions installed it, it will now be removed.)

## ShellCheck and shfmt

In the development environment, the `tools/setup/install-shellcheck`
and `tools/setup/install-shfmt` scripts download binaries for
ShellCheck and shfmt from GitHub, check them against a known hash, and
install them to `/usr/local/bin`. These tools are run as part of the
[linting system](../testing/linters.md).

## Puppet packages

Third-party puppet modules are downloaded from the Puppet Forge into
subdirectories under `/srv/zulip-puppet-cache`, hashed based on their
versions; the latest is always symlinked as
`/srv/zulip-puppet-cache/current`. `zulip-puppet-apply` installs
these dependencies immediately before they are needed.

## Other third-party and generated files

In this section, we discuss the other third-party dependencies,
generated code, and other files whose original primary source is not
the Zulip server repository, and how we provision and otherwise
maintain them.

### Emoji

Zulip uses the [iamcal emoji data package][iamcal] for its emoji data
and sprite sheets. We download this dependency using `npm`, and then
have a tool, `tools/setup/build_emoji`, which reformats the emoji data
into the files under `static/generated/emoji`. Those files are in
turn used by our [Markdown processor](markdown.md) and
`tools/update-prod-static` to make Zulip's emoji work in the various
environments where they need to be displayed.

Since processing emoji is a relatively expensive operation, as part of
optimizing provisioning, we use the same caching strategy for the
compiled emoji data as we use for virtualenvs and `node_modules`
directories, with `scripts/lib/clean_emoji_cache.py` responsible for
garbage-collection. This caching and garbage-collection is required
because a correct emoji implementation involves over 1000 small image
files and a few large ones. There is a more extended article on our
[emoji infrastructure](emoji.md).

### Translations data

Zulip's [translations infrastructure](../translating/translating.md) generates
several files from the source data, which we manage similar to our
emoji, but without the caching (and thus without the
garbage-collection). New translations data is downloaded from
Transifex and then compiled to generate both the production locale
files and also language data in `locale/language*.json` using
`manage.py compilemessages`, which extends the default Django
implementation of that tool.

### Pygments data

The list of languages supported by our Markdown syntax highlighting
comes from the [pygments][] package. `tools/setup/build_pygments_data` is
responsible for generating `web/generated/pygments_data.json` so that
our JavaScript Markdown processor has access to the supported list.

## Modifying provisioning

When making changes to Zulip's provisioning process or dependencies,
usually one needs to think about making changes in 3 places:

- `tools/lib/provision.py`. This is the main provisioning script,
  used by most developers to maintain their development environment.
- `docs/development/dev-setup-non-vagrant.md`. This is our "manual installation"
  documentation. Strategically, we'd like to move the support for more
  versions of Linux from here into `tools/lib/provision.py`.
- Production. Our tools for compiling/generating static assets need
  to be called from `tools/update-prod-static`, which is called by
  `tools/build-release-tarball` (for doing Zulip releases) as well as
  `tools/upgrade-zulip-from-git` (for deploying a Zulip server off of
  `main`).

[virtualenv]: https://virtualenv.pypa.io/en/stable/
[virtualenv-clone]: https://github.com/edwardgeorge/virtualenv-clone/
[pnpm]: https://pnpm.io/
[npm]: https://npmjs.com/
[iamcal]: https://github.com/iamcal/emoji-data
[pygments]: https://pygments.org/
