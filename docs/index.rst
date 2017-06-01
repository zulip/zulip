.. zulip documentation master file, created by
   sphinx-quickstart on Mon Aug 17 16:24:04 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Zulip documentation!
===============================

Zulip is a powerful, open source group chat application. Written in
Python and using the Django framework, Zulip supports both private
messaging and group chats via conversation streams.

Zulip also supports fast search, drag-and-drop file uploads, image
previews, group private messages, audible notifications, missed-message
emails, desktop apps, and much more.

Further information on the Zulip project and its features can be found
at `https://www.zulip.org <https://www.zulip.org>`__ and in these
docs.  Our code is available at `our GitHub repository
<https://github.com/zulip/>`__.

This set of documents covers installation and contribution instructions.

Contents:

* :ref:`overview`
* :ref:`zulip-in-production`
* :ref:`development-environment`
* :ref:`developer-tutorials`
* :ref:`code-contribution-guide`
* :ref:`code-testing`
* :ref:`subsystem-documentation`

.. _overview:

.. toctree::
   :maxdepth: 2
   :caption: Overview

   readme-symlink
   architecture-overview
   directory-structure
   roadmap
   changelog

.. _zulip-in-production:

.. toctree::
   :maxdepth: 2
   :caption: Zulip in production

   prod-requirements
   Installing a production server <prod-install>
   prod-troubleshooting
   prod-customize
   prod-mobile-push-notifications
   prod-maintain-secure-upgrade
   security-model
   prod-authentication-methods
   prod-postgres

.. _development-environment:

.. toctree::
   :maxdepth: 2
   :caption: Development environment

   Development environment installation <dev-overview>
   Recommended setup (Vagrant) <dev-env-first-time-contributors>
   Advanced setup (non-Vagrant) <dev-setup-non-vagrant>
   Using the development environment <using-dev-environment>
   Developing remotely <dev-remote>

.. _developer-tutorials:

.. toctree::
   :maxdepth: 2
   :caption: Developer tutorials

   integration-guide
   webhook-walkthrough
   new-feature-tutorial
   writing-views
   life-of-a-request
   reading-list

.. _code-contribution-guide:

.. toctree::
   :maxdepth: 2
   :caption: Code contribution guide

   git-guide
   version-control
   code-style
   mypy
   code-reviewing
   chat-zulip-org
   zulipbot-usage
   accessibility

.. _code-testing:

.. toctree::
   :maxdepth: 2
   :caption: Code testing

   testing
   linters
   testing-with-node
   testing-with-django
   testing-with-casper
   manual-testing

.. _subsystem-documentation:

.. toctree::
   :maxdepth: 2
   :caption: Subsystem documentation

   settings
   events-system
   queuing
   bots-guide
   custom-apps
   pointer
   markdown
   realms
   front-end-build-process
   schema-migrations
   html_css
   hashchange-system
   emoji
   full-text-search
   analytics
   translating
   client
   logging
   release-checklist
   api-release-checklist
   README
   user-docs
