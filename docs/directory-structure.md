# Directory structure

This page documents the Zulip directory structure and how to decide
where to put a file.

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

### Bots

* `api/integrations/` Bots distributed as part of the Zulip API bundle.

* `bots/` Previously Zulip internal bots. These usually need a bit of
   work.

-----------------------------------------------------

### Management commands

* `zerver/management/commands/` Management commands one might run at a
  production deployment site (e.g. scripts to change a value or
  deactivate a user properly)

-------------------------------------------------------------------------

### Views

* `zerver/tornadoviews.py` Tornado views

* `zerver/views/webhooks.py` Webhook views

* `zerver/views/messages.py` message-related views

* `zerver/views/__init__.py` other Django views

----------------------------------------

### Jinja2 Compatibility Files

* `zproject/jinja2/__init__.py` Jinja2 environment

* `zproject/jinja2/backends.py` Jinja2 backend

* `zproject/jinja2/compressors.py` Jinja2 compatible functions of
   Django-Pipeline

-----------------------------------------------------------------------

### Static assets

* `assets/` For assets not to be served to the web (e.g. the system to
            generate our favicons)

* `static/` For things we do want to both serve to the web and
            distribute to production deployments (e.g. the webpages)

---------------------------------------------------------------

### Puppet

* `puppet/zulip/` For configuration for production deployments

-------------------------------------------------------------------

### Templates

* `templates/zerver/` For Jinja2 templates for the backend (for zerver app)

* `static/templates/` Handlebars templates for the frontend

-----------------------------------------------------------------------

### Tests

* `zerver/tests/` Backend tests

* `frontend_tests/node_tests/` Node Frontend unit tests

* `frontend_tests/casper_tests/` Casper frontend tests

-----------------------------------------------------------------------


### Documentation

*  `docs/`        Source for this documentation

--------------------------------------------------------------

You can consult the repository's `.gitattributes` file to see exactly
which components are excluded from production releases (release
tarballs are generated using `tools/build-release-tarball`).
