===================
Directory structure
===================

.. attention::
   Needs content review

This page documents our directory structure and how to decide where to
put a file.

Scripts
=======

+----------------------+-----------------------------------------------------------------------------------+
| ``scripts/``         | Scripts that local server users might run manually (e.g. ``restart/server``)      |
+----------------------+-----------------------------------------------------------------------------------+
| ``bin/``             | Scripts that are needed on local server deployments but humans should never run   |
+----------------------+-----------------------------------------------------------------------------------+
| ``scripts/setup/``   | Tools that local server installations will only run once, during installation     |
+----------------------+-----------------------------------------------------------------------------------+
| ``tools/``           | Internal tools (not distributed)                                                  |
+----------------------+-----------------------------------------------------------------------------------+

Bots
====

+------------------------+---------------------------------------------------+
| ``bots/``              | Not distributed, even to local server instances   |
+------------------------+---------------------------------------------------+
| ``api/integrations``   | Distributed in our API bundle                     |
+------------------------+---------------------------------------------------+

Management commands
===================

+-------------------------------------+---------------------------------------------------------------------------------------------------------------------------+
| ``zerver/management/commands/``     | Management commands one might run at a local server site (e.g. scripts to change a value or deactivate a user properly)   |
+-------------------------------------+---------------------------------------------------------------------------------------------------------------------------+
| ``zilencer/management/commands/``   | Management commands for internal use only (e.g. analytics)                                                                |
+-------------------------------------+---------------------------------------------------------------------------------------------------------------------------+

Views
=====

+--------------------------------+-----------------------------------------+
| ``zilencer/views.py``          | Internal-only views (analytics, etc.)   |
+--------------------------------+-----------------------------------------+
| ``zerver/tornadoviews.py``     | Tornado views                           |
+--------------------------------+-----------------------------------------+
| ``zerver/views/webhooks.py``   | Webhook views                           |
+--------------------------------+-----------------------------------------+
| ``zerver/views/__init__.py``   | other Django views                      |
+--------------------------------+-----------------------------------------+

Static assets
=============

+---------------+----------------------------------------------------------------------------------------------------------------+
| ``assets/``   | For assets not to be served to the web (e.g. the system to generate our favicons, or our tshirt design data)   |
+---------------+----------------------------------------------------------------------------------------------------------------+
| ``static/``   | For things we do want to both server to the web and distribute to local server users (e.g. the webpages)       |
+---------------+----------------------------------------------------------------------------------------------------------------+

Puppet
======

+-----------------------------+-------------------------------------------------------------------------------------------------------------------------------------+
| ``puppet/zulip``            | For common configuration relevant to both internal servers and local server (e.g. configuration to run our app, supervisor, etc.)   |
+-----------------------------+-------------------------------------------------------------------------------------------------------------------------------------+
| ``puppet/zulip-internal``   | For configuration for our internal servers (e.g. SSH setup, Nagios setup)                                                           |
+-----------------------------+-------------------------------------------------------------------------------------------------------------------------------------+

Templates
=========

+--------------------------+----------------------------------------------------------------------------------------------------------------------+
| ``templates/zerver``     | For templates related to zerver views.                                                                               |
+--------------------------+----------------------------------------------------------------------------------------------------------------------+
| ``templates/zilencer``   | For templates related to zilencer views, including random other pages from our corporate website (e.g. job posts).   |
+--------------------------+----------------------------------------------------------------------------------------------------------------------+

You can consult the code for ``tools/build-local-server-tarball`` to
check exactly which components are shipped along with local server --
since that is the tool that does the builds, it controls the
distribution.
