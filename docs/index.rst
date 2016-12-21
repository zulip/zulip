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

* :ref:`user-docs`
* :ref:`prod-install-docs`
* :ref:`dev-install-docs`
* :ref:`tutorial-docs`
* :ref:`code-docs`
* :ref:`code-testing`
* :ref:`system-docs`

.. _user-docs:

.. toctree::
   :maxdepth: 2
   :caption: Overview

   readme-symlink
   architecture-overview
   directory-structure
   roadmap
   changelog

.. _prod-install-docs:

.. toctree::
   :maxdepth: 2
   :caption: Zulip in production

   prod-requirements
   Installing a production server <prod-install>
   prod-troubleshooting
   prod-customize
   prod-maintain-secure-upgrade
   prod-authentication-methods
   prod-postgres

.. _dev-install-docs:

.. toctree::
   :maxdepth: 2
   :caption: Development environment

   Development environment installation <dev-overview>
   Recommended setup (Vagrant) <dev-env-first-time-contributors>
   Advanced setup (non-Vagrant) <dev-setup-non-vagrant>
   Using the development environment <using-dev-environment>
   Developing remotely <dev-remote>

.. _tutorial-docs:

.. toctree::
   :maxdepth: 2
   :caption: Developer tutorials

   integration-guide
   new-feature-tutorial
   writing-views
   life-of-a-request

.. _code-docs:

.. toctree::
   :maxdepth: 2
   :caption: Code contribution guide

   git-guide
   version-control
   code-style
   mypy
   code-reviewing

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

.. _system-docs:

.. toctree::
   :maxdepth: 2
   :caption: Subsystem documentation

   settings
   queuing
   bots-guide
   custom-apps
   pointer
   markdown
   realms
   front-end-build-process
   schema-migrations
   html_css
   full-text-search
   translating
   logging
   release-checklist
   README
