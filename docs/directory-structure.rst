===================
Directory structure
===================

.. attention::

This page documents our directory structure and how to decide where to
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
| ``bots/``              | Not distributed, even to production deployment instances             |
+------------------------+----------------------------------------------------------------------+
| ``api/integrations``   | Distributed in our API bundle                                        |
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

+------------------------+---------------------------------+
| ``zerver/test*.py``    | Backend tests                   |
+------------------------+---------------------------------+
| ``zerver/tests``       | Frontend tests                  |
+------------------------+---------------------------------+

Documentation
=============

+-------------+-----------------------------------------------+
| ``docs/``   | Source for this documentation                 |
+-------------+-----------------------------------------------+

You can consult the .gitattributes file to see exactly which
components are excluded from production releases (release tarballs are
generated using tools/build-release-tarball).
