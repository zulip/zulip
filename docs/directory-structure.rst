===================
Directory structure
===================

This page documents the Zulip directory structure and how to decide where to
put a file.

Scripts
=======

+--------------------+-----------------------------------------------------------------------------------+
| ``scripts/``       | Scripts that production deployments might run manually (e.g. ``restart-server``)  |
+--------------------+-----------------------------------------------------------------------------------+
| ``bin/``           | Scripts that are needed on production deployments but humans should never run     |
+--------------------+-----------------------------------------------------------------------------------+
| ``scripts/setup/`` | Tools that production deployments will only run once, during installation         |
+--------------------+-----------------------------------------------------------------------------------+
| ``tools/``         | Development tools                                                                 |
+--------------------+-----------------------------------------------------------------------------------+

Bots
====

+------------------------+----------------------------------------------------------------------+
| ``api/integrations``   | Bots distributed as part of the Zulip API bundle.                    |
+------------------------+----------------------------------------------------------------------+
| ``bots/``              | Previously Zulip internal bots.  These usually need a bit of work.   |
+------------------------+----------------------------------------------------------------------+

Management commands
===================

+-------------------------------------+------------------------------------------------------------------------------------------------------------------------------------+
| ``zerver/management/commands/``     | Management commands one might run at a production deployment site (e.g. scripts to change a value or deactivate a user properly)   |
+-------------------------------------+------------------------------------------------------------------------------------------------------------------------------------+

Views
=====

+--------------------------------+-----------------------------------------+
| ``zerver/tornadoviews.py``     | Tornado views                           |
+--------------------------------+-----------------------------------------+
| ``zerver/views/webhooks.py``   | Webhook views                           |
+--------------------------------+-----------------------------------------+
| ``zerver/views/messages.py``   | message-related views                   |
+--------------------------------+-----------------------------------------+
| ``zerver/views/__init__.py``   | other Django views                      |
+--------------------------------+-----------------------------------------+

Static assets
=============

+---------------+---------------------------------------------------------------------------------------------------------------+
| ``assets/``   | For assets not to be served to the web (e.g. the system to generate our favicons)                             |
+---------------+---------------------------------------------------------------------------------------------------------------+
| ``static/``   | For things we do want to both serve to the web and distribute to production deployments (e.g. the webpages)   |
+---------------+---------------------------------------------------------------------------------------------------------------+

Puppet
======

+--------------------+----------------------------------------------------------------------------------+
| ``puppet/zulip``   | For configuration for production deployments                                     |
+--------------------+----------------------------------------------------------------------------------+

Templates
=========

+--------------------------+--------------------------------------------------------+
| ``templates/zerver``     | For templates related to zerver views                  |
+--------------------------+--------------------------------------------------------+
| ``static/templates``     | Handlebars templates for the frontend                  |
+--------------------------+--------------------------------------------------------+

Tests
=====

+------------------------+-----------------------------------+
| ``zerver/test*.py``             | Backend tests            |
+------------------------+-----------------------------------+
| ``frontend_tests/node``         | Node Frontend unit tests |
+------------------------+-----------------------------------+
| ``frontend_tests/tests``        | Casper frontend tests    |
+------------------------+-----------------------------------+

Documentation
=============

+-------------+-----------------------------------------------+
| ``docs/``   | Source for this documentation                 |
+-------------+-----------------------------------------------+

You can consult the repository's .gitattributes file to see exactly
which components are excluded from production releases (release
tarballs are generated using tools/build-release-tarball).
