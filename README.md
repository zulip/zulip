# Zulip overview

## Table of Contents
- [Zulip Overview](#zulip-overview)
- [Getting Started](#getting-started)
  - [Contributing Code](#contributing-code)
  - [Contributing Non-Code](#contributing-non-code)
  - [Running a Zulip Server](#running-a-zulip-server)
  - [Using Zulip Without a Server](#using-zulip-without-setting-up-a-server)
- [Third-Party Integrations](#third-party-integrations)
- [Troubleshooting Installation](#troubleshooting-installation)


[Zulip](https://zulip.com) is an open-source team collaboration tool with unique
[topic-based threading][why-zulip] that combines the best of email and chat to
make remote work productive and delightful. Fortune 500 companies, [leading open
source projects][rust-case-study], and thousands of other organizations use
Zulip every day. Zulip is the only [modern team chat app][features] that is
designed for both live and asynchronous conversations.

Zulip is built by a distributed community of developers from all around the
world, with 74+ people who have each contributed 100+ commits. With
over 1000 contributors merging over 500 commits a month, Zulip is the
largest and fastest growing open source team chat project.

Come find us on the [development community chat](https://zulip.com/development-community/)!

[![GitHub Actions build status](https://github.com/zulip/zulip/actions/workflows/zulip-ci.yml/badge.svg)](https://github.com/zulip/zulip/actions/workflows/zulip-ci.yml?query=branch%3Amain)
[![coverage status](https://img.shields.io/codecov/c/github/zulip/zulip/main.svg)](https://codecov.io/gh/zulip/zulip)
[![Mypy coverage](https://img.shields.io/badge/mypy-100%25-green.svg)][mypy-coverage]
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![code style: prettier](https://img.shields.io/badge/code_style-prettier-ff69b4.svg)](https://github.com/prettier/prettier)
[![GitHub release](https://img.shields.io/github/release/zulip/zulip.svg)](https://github.com/zulip/zulip/releases/latest)
[![docs](https://readthedocs.org/projects/zulip/badge/?version=latest)](https://zulip.readthedocs.io/en/latest/)
[![Zulip chat](https://img.shields.io/badge/zulip-join_chat-brightgreen.svg)](https://chat.zulip.org)
[![Twitter](https://img.shields.io/badge/twitter-@zulip-blue.svg?style=flat)](https://twitter.com/zulip)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/zulip)](https://github.com/sponsors/zulip)

[mypy-coverage]: https://blog.zulip.org/2016/10/13/static-types-in-python-oh-mypy/
[why-zulip]: https://zulip.com/why-zulip/
[rust-case-study]: https://zulip.com/case-studies/rust/
[features]: https://zulip.com/features/

## Getting started

- **Contributing code**. Check out our [guide for new
  contributors](https://zulip.readthedocs.io/en/latest/contributing/contributing.html)
  to get started. We have invested in making Zulip’s code highly
  readable, thoughtfully tested, and easy to modify. Beyond that, we
  have written an extraordinary 150K words of documentation for Zulip
  contributors.

  ### Testing Changes Locally
Before submitting a pull request, it's essential to test your changes thoroughly. Follow these steps to set up a local testing environment:

1. Run the backend test suite using the following command:
   ```bash
   ./tools/test-backend
   ```
   This will run Zulip's backend tests to ensure nothing is broken in the server-side logic.
2. To run frontend tests, use:
   ```bash
   ./tools/test-frontend
   ```
   This command ensures that your changes to the frontend do not break any of Zulip’s user interface or client-side functionality.
3. If you're adding new functionality, write corresponding unit tests in the appropriate directories (e.g., `zerver/tests` for backend tests).
4. Make sure all tests pass before submitting your pull request. You can find more details in the [testing guide](https://zulip.readthedocs.io/en/latest/testing/testing.html).


- **Contributing non-code**. [Report an
  issue](https://zulip.readthedocs.io/en/latest/contributing/contributing.html#reporting-issues),
  [translate](https://zulip.readthedocs.io/en/latest/translating/translating.html)
  Zulip into your language, or [give us
  feedback](https://zulip.readthedocs.io/en/latest/contributing/contributing.html#user-feedback).
  We'd love to hear from you, whether you've been using Zulip for years, or are just
  trying it out for the first time.

- **Checking Zulip out**. The best way to see Zulip in action is to drop by the
  [Zulip community server](https://zulip.com/development-community/). We also
  recommend reading about Zulip's [unique
  approach](https://zulip.com/why-zulip/) to organizing conversations.

- **Running a Zulip server**. Self-host Zulip directly on Ubuntu or Debian
  Linux, in [Docker](https://github.com/zulip/docker-zulip), or with prebuilt
  images for [Digital Ocean](https://marketplace.digitalocean.com/apps/zulip) and
  [Render](https://render.com/docs/deploy-zulip).
  Learn more about [self-hosting Zulip](https://zulip.com/self-hosting/).
  
  ### Troubleshooting Installation
If you're running into issues while setting up a Zulip server on non-standard environments like Windows or ARM-based devices, here are some tips:
- **ARM-Based Devices**: You may need to manually compile certain dependencies that aren't available by default. Ensure you're using the correct architecture-specific libraries.
- **Windows**: We recommend using Windows Subsystem for Linux (WSL) to run Zulip smoothly. Running directly on Windows may cause issues due to missing dependencies or unsupported system packages.
- **General Tips**:
  - Ensure you're using the correct version of Python and other system dependencies.
  - If you're using Docker, make sure that Docker is set up with appropriate permissions and resource allocations.
  - Check Zulip’s [installation guide](https://zulip.readthedocs.io/en/latest/production/install.html) for more detailed troubleshooting instructions.
 
  ### Third-Party Integrations

Zulip integrates with a wide range of third-party services. Here are steps for integrating Zulip with some popular platforms:

- **Google Drive**:
  1. Enable the Google Drive API from your Google Cloud Console.
  2. Generate OAuth2 credentials for your Zulip instance and update your Zulip configuration file with these credentials.
  3. Once set up, users can easily attach files directly from Google Drive into their Zulip messages.

- **JIRA**:
  1. Set up a webhook in JIRA that points to your Zulip server's webhook handler.
  2. In your JIRA admin settings, configure the Zulip API key and select which events (e.g., new issues, status updates) should trigger notifications in Zulip streams.
  3. Zulip will automatically post updates from JIRA to the relevant stream.

For more integrations, see Zulip’s [full integration guide](https://zulip.com/integrations/).

- **Using Zulip without setting up a server**. Learn about [Zulip
  Cloud](https://zulip.com/plans/) hosting options. Zulip sponsors free [Zulip
  Cloud Standard](https://zulip.com/plans/) for hundreds of worthy
  organizations, including [fellow open-source
  projects](https://zulip.com/for/open-source/).

- **Participating in [outreach
  programs](https://zulip.readthedocs.io/en/latest/contributing/contributing.html#outreach-programs)**
  like [Google Summer of Code](https://developers.google.com/open-source/gsoc/)
  and [Outreachy](https://www.outreachy.org/).

- **Supporting Zulip**. Advocate for your organization to use Zulip, become a
  [sponsor](https://github.com/sponsors/zulip), write a review in the mobile app
  stores, or [help others find
  Zulip](https://zulip.readthedocs.io/en/latest/contributing/contributing.html#help-others-find-zulip).

You may also be interested in reading our [blog](https://blog.zulip.org/), and
following us on [Twitter](https://twitter.com/zulip) and
[LinkedIn](https://www.linkedin.com/company/zulip-project/).

Zulip is distributed under the
[Apache 2.0](https://github.com/zulip/zulip/blob/main/LICENSE) license.
