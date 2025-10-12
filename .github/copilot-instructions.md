<!--
Purpose: concise, actionable guidance for AI coding agents working on Zulip.
Keep this short (~20-50 lines). Do not repeat generic guidance; focus on
project-specific patterns, locations, and commands that make an agent
productive quickly.
-->

# Zulip — Copilot instructions (concise)

- Big picture
  - Backend: Django project composed of multiple Django apps. The primary
    backend apps live under `zerver/` (core HTTP/API logic) and `zilencer/`
    (email/bridge workers). Top-level Django settings are in `zproject/`.
  - Frontend: static assets and TS/JS live under `web/` (ESM + webpack).
    Application source for the portico/landing/login UI is in `web/src`.
  - Dev server: `tools/run-dev` starts a local reverse-proxy that runs
    Django, Tornado (real-time push), webpack dev server, tusd and other
    helpers. Use this over invoking Django's `runserver` directly when
    testing integrated flows.

- Key files to reference
  - `manage.py` — entry for Django management commands; production wrapper
    that expects `zproject.settings` (or `zproject.test_settings` for tests).
  - `tools/run-dev` — starts the integrated local dev environment (ports
    default to 9991..). Supports `--test`, `--streamlined`, `--minify`,
    `--help-center-*` options. Non-root only.
  - `tools/webpack` and `web/` — frontend build/watch tooling. `starlight_help`
    contains the help-center (Astro) site served by run-dev in dev mode.
  - `zproject/` — settings split across `default_settings.py`,
    `prod_settings_template.py`, `dev_settings.py`, and `computed_settings.py`.
  - `pyproject.toml` and `package.json` — pinned dependencies and developer
    tooling (Python & Node). See `pyproject.toml` dev group for test/lint tools.

- Typical developer workflows (explicit commands)
  - Start full integrated dev server (serves backend, Tornado, webpack):
    ./tools/run-dev
  - Run run-dev in test mode (ports shifted, used by Puppeteer tests):
    ./tools/run-dev --test
  - Run a single Django management command (e.g., migrations):
    ./manage.py migrate --settings=zproject.settings
  - Build frontend assets once (CI/test mode):
    ./tools/webpack --test

- Testing notes
  - Puppeteer browser tests and many integration tests expect `run-dev` to
    be running. See `tools/test-run-dev` and `docs/testing/*.md` for details.
  - Unit/backend tests use Django test runner via `./manage.py test`.

- Patterns & conventions useful to follow
  - Prefer modifying existing Django apps under `zerver/` for HTTP/API logic.
  - Use `zproject/computed_settings.py` for values derived from configured
    settings; add public/templated server settings to `prod_settings_template.py`.
  - The dev environment is opinionated: `run-dev` acts as nginx and clears
    memcached by default; avoid modifying startup behavior without checking
    `tools/run-dev`.
  - Frontend code is bundled with webpack; hot-reload is provided by the
    webpack dev server. For help center local dev, `starlight_help` uses
    `pnpm dev` and is proxied by `run-dev`.

- Integration points and external dependencies
  - PostgreSQL (psycopg2), memcached, Redis, RabbitMQ (pika) are used in prod
    and emulated in dev via provisioning scripts; `run-dev` expects these to
    be available when running a full dev environment.
  - Many third-party integrations are optional and configured via
    `/etc/zulip/settings.py` or dev secrets (see `zproject/dev-secrets.conf`).

- Quick examples for code locations
  - Add a new API view: `zerver/views/` (follow existing `zerver/views/*` files)
  - Add a new management command: `zerver/management/commands/your_command.py`
  - Frontend component: `web/src/<area>/...` (e.g., `web/src/portico` for header)

- When in doubt
  - Prefer seeking the corresponding doc under `docs/` (there are many
    subsystem docs like `docs/subsystems/*` and `docs/development/*`).
  - For environment-specific behavior check `zproject/dev_settings.py` and
    `zproject/prod_settings_template.py` rather than guessing from runtime.

Please review and tell me which areas you want expanded (testing, CI,
frontend build, or deployment). I can iterate quickly. 
