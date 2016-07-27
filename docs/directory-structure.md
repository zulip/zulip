# Directory structure

This page documents the Zulip directory structure, where to find
things, and how to decide where to put a file.

You may also find the [new application feature
tutorial](new-feature-tutorial.html) helpful for understanding the
flow through these files.

### Core Python files

Zulip uses the [Django web
framework](https://docs.djangoproject.com/en/1.8/), so a lot of these
paths will be familiar to Django developers.

* `zproject/urls.py` Main [Django routes file](https://docs.djangoproject.com/en/1.8/topics/http/urls/).  Defines which URLs are handled by which view functions or templates.

* `zerver/models.py` Main [Django models](https://docs.djangoproject.com/en/1.8/topics/db/models/) file.  Defines Zulip's database tables.

* `zerver/lib/actions.py` Most code doing writes to user-facing database tables.

* `zerver/views/*.py` Most [Django views](https://docs.djangoproject.com/en/1.8/topics/http/views/).

* `zerver/views/webhooks/` Webhook views for [Zulip integrations](integration-guide.html).

* `zerver/tornadoviews.py` Tornado views.

* `zerver/worker/queue_processors.py` [Queue workers](queuing.html).

* `zerver/lib/*.py` Most library code.

* `zerver/lib/bugdown/` [Backend Markdown processor](markdown.html).

* `zproject/backends.py` [Authentication backends](https://docs.djangoproject.com/en/1.8/topics/auth/customizing/).

-------------------------------------------------------------------

### HTML Templates

See [our translating docs](translating.html) for details on Zulip's
templating systems.

* `templates/zerver/` For [Jinja2](http://jinja.pocoo.org/) templates for the backend (for zerver app).

* `static/templates/` [Handlebars](http://handlebarsjs.com/) templates for the frontend.

----------------------------------------

### JavaScript and other static assets

* `static/js/` Zulip's own JavaScript.

* `static/styles/` Zulip's own CSS.

* `static/images/` Zulip's images.

* `static/third/` Third-party JavaScript and CSS that has been vendored.

* `node_modules/` Third-party JavaScript installed via `npm`.

* `assets/` For assets not to be served to the web (e.g. the system to
            generate our favicons).

-----------------------------------------------------------------------

### Tests

* `zerver/tests/` Backend tests.

* `frontend_tests/node_tests/` Node Frontend unit tests.

* `frontend_tests/casper_tests/` Casper frontend tests.

* `tools/test-*` Developer-facing test runner scripts.

-----------------------------------------------------

### Management commands

These are distinguished from scripts, below, by needing to run a
Django context (i.e. with database access).

* `zerver/management/commands/` Management commands one might run at a
  production deployment site (e.g. scripts to change a value or
  deactivate a user properly).

---------------------------------------------------------------

### Scripts

* `scripts/` Scripts that production deployments might run manually
  (e.g., `restart-server`).

* `scripts/lib/` Scripts that are needed on production deployments but
  humans should never run directly.

* `scripts/setup/` Scripts that production deployments will only run
  once, during installation.

* `tools/` Scripts used only in a Zulip development environment.
  These are not included in production release tarballs for Zulip, so
  that we can include scripts here one wouldn't want someone to run in
  production accidentally (e.g. things that delete the Zulip database
  without prompting).

* `tools/setup/` Subdirectory of `tools/` for things only used during
  the development environment setup process.

* `tools/travis/` Subdirectory of `tools/` for things only used to
  setup and run our tests in Travis CI.  Actually test suites should
  go in `tools/`.

---------------------------------------------------------

### API and Bots

* `api/` Zulip's Python API bindings (released separately).

* `api/examples/` API examples.

* `api/integrations/` Bots distributed as part of the Zulip API bundle.

* `bots/` Previously Zulip internal bots. These usually need a bit of
   work.

-------------------------------------------------------------------------

### Production puppet configuration

This is used to deploy essentially all configuration in production.

* `puppet/zulip/` For configuration for production deployments.

* `puppet/zulip/manifests/voyager.pp` Main manifest for Zulip standalone deployments.

-----------------------------------------------------------------------

### Additional Django apps

* `confirmation` Email confirmation system.

* `analytics` Analytics for the Zulip server administrator (needs work to
  be useful to normal Zulip sites).

* `corporate` The old Zulip.com website.  Not included in production
  distribution.

* `zilencer` Primarily used to hold management commands that aren't
  used in production.  Not included in production distribution.

-----------------------------------------------------------------------

### Jinja2 Compatibility Files

* `zproject/jinja2/__init__.py` Jinja2 environment.

* `zproject/jinja2/backends.py` Jinja2 backend.

* `zproject/jinja2/compressors.py` Jinja2 compatible functions of
   Django-Pipeline.

-----------------------------------------------------------------------

### Translation files

* `locale/` Backend (Django) translations data files.

* `static/locale/` Frontend translations data files.

-----------------------------------------------------------------------

### Documentation

*  `docs/`        Source for this documentation.

--------------------------------------------------------------

You can consult the repository's `.gitattributes` file to see exactly
which components are excluded from production releases (release
tarballs are generated using `tools/build-release-tarball`).
