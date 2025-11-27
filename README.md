# nodl-chat

nodl-chat is a fork of [Zulip](https://zulip.com) with custom extensions for the nodl platform. It provides real-time team chat with Supabase authentication integration.

## Project Overview

This repository extends Zulip with nodl-specific features:
- **Supabase JWT Authentication** - Integrate with nodl's auth system
- **User/Workspace Sync** - Synchronize users and workspaces with nodl-backend
- **Extension Models** - Custom data models for nodl features
- **R2 Storage Backend** - Cloudflare R2 integration for file storage
- **Additional API Endpoints** - REST APIs for nodl-specific operations

All nodl customizations are contained in the `nodl/` directory to minimize merge conflicts with upstream Zulip.

## Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Node.js 18+ (for frontend assets)
- Git

## Quick Start

### 1. Clone the Repository

```bash
git clone git@github.com:Duatadmin/nodl-chat.git
cd nodl-chat
```

### 2. Run Setup Script

```bash
./scripts/setup-dev.sh
```

### 3. Activate Virtual Environment

```bash
source venv/bin/activate
```

### 4. Run Development Server

```bash
python manage.py runserver
```

## Development Workflow

### Project Structure

```
nodl-chat/
├── nodl/                    # All nodl customizations
│   ├── auth/               # Supabase JWT middleware
│   ├── sync/               # User/workspace sync
│   ├── extensions/         # Extension models
│   ├── storage/            # R2 storage backend
│   ├── api/                # Additional REST endpoints
│   └── tests/              # nodl-specific tests
├── zerver/                  # Zulip core (minimal modifications)
├── zproject/                # Django project settings
└── scripts/                 # Development scripts
```

### Making Changes

1. **nodl code**: Add to `nodl/` directory
2. **Zulip modifications**: Use NODL MODIFICATION markers:
   ```python
   # NODL MODIFICATION START - [Description]
   # Reason: [Why this change is needed]
   # Date: [Date]
   [code]
   # NODL MODIFICATION END
   ```

### Code Style

| Tool | Purpose |
|------|---------|
| Ruff | Linting + formatting |
| mypy | Type checking (strict mode) |

Configuration in `ruff.toml` and `mypy.ini`.

## Testing

### Run All Tests

```bash
./scripts/run-tests.sh
```

### Run Specific Tests

```bash
# nodl tests only
pytest nodl/tests/ -v

# Linting
ruff check nodl/

# Type checking
mypy nodl/ --ignore-missing-imports
```

## Deployment

### Railway Deployment

The project is configured for Railway deployment:
- `nixpacks.toml` - Build configuration
- `supervisord.conf` - Process management
- `nginx.conf` - HTTP/WebSocket routing

### Environment Variables

Required environment variables for production:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Django secret key
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_ANON_KEY` - Supabase anonymous key

## Syncing with Upstream Zulip

```bash
# Fetch upstream changes
git fetch upstream

# Merge upstream main
git merge upstream/main

# Resolve conflicts (prioritize nodl/ changes)
```

## Fork Information

- **Upstream**: https://github.com/zulip/zulip
- **Fork Commit**: `cd67aef4aa3a7c42756781d948fe1ebc4d047ef2`
- **Fork Date**: 2024-11-27

---

# Zulip overview

[Zulip](https://zulip.com) is an open-source team collaboration tool with unique
[topic-based threading][why-zulip] that combines the best of email and chat to
make remote work productive and delightful. Fortune 500 companies, [leading open
source projects][rust-case-study], and thousands of other organizations use
Zulip every day. Zulip is the only [modern team chat app][features] that is
designed for both live and asynchronous conversations.

Zulip is built by a distributed community of developers from all around the
world, with 97+ people who have each contributed 100+ commits. With
over 1,500 contributors merging over 500 commits a month, Zulip is the
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
  have written an extraordinary 185K words of documentation for Zulip
  contributors.

- **Contributing non-code**. [Report an
  issue](https://zulip.readthedocs.io/en/latest/contributing/contributing.html#reporting-issues),
  [translate](https://zulip.readthedocs.io/en/latest/translating/translating.html)
  Zulip into your language, or [give us
  feedback](https://zulip.readthedocs.io/en/latest/contributing/suggesting-features.html).
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
