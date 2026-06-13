# Using the development environment

This page describes the basic edit/refresh workflows for working with
the Zulip development environment. Generally, the development
environment will automatically update as soon as you save changes
using your editor. Details for work on the [server](#server),
[web app](#web), and [mobile apps](#mobile) are below.

If you're working on authentication methods or need to use the [Zulip
REST API][rest-api], which requires an API key, see [authentication in
the development environment][authentication-dev-server].

## Common

- Zulip's `main` branch moves quickly, and you should rebase
  constantly with, for example,
  `git fetch upstream; git rebase upstream/main` to avoid developing
  on an old version of the Zulip codebase (leading to unnecessary
  merge conflicts).
- Remember to run `tools/provision` to update your development
  environment after switching branches; it will run in under a second
  if no changes are required.
- After making changes, you'll often want to run the
  [linters](../testing/linters.md) and relevant [test
  suites](../testing/testing.md). Consider using our [Git pre-commit
  hook](../git/zulip-tools.md#set-up-git-repo-script) to
  automatically lint whenever you make a commit.
- All of our test suites are designed to support quickly testing just
  a single file or test case, which you should take advantage of to
  save time.
- Many useful development tools, including tools for rebuilding the
  database with different test data, are documented in-app at
  `https://localhost:9991/devtools`.
- If you want to restore your development environment's database to a
  pristine state, you can use `./tools/rebuild-dev-database`.

## Server

- For changes that don't affect the database model, the Zulip
  development environment will automatically detect changes and
  restart:
  - The main Django/Tornado server processes are run on top of
    Django's [manage.py runserver][django-runserver], which will
    automatically restart them when you save changes to Python code
    they use. You can watch this happen in the `run-dev` console
    to make sure the backend has reloaded.
  - The Python queue workers will also automatically restart when you
    save changes, as long as they haven't crashed (which can happen if
    they reloaded into a version with a syntax error).
- If you change the database schema (`zerver/models/*.py`), you'll need
  to use the [Django migrations
  process](../subsystems/schema-migrations.md); see also the [new
  feature tutorial][new-feature-tutorial] for an example.
- While testing server changes, it's helpful to watch the `run-dev`
  console output, which will show tracebacks for any 500 errors your
  Zulip development server encounters (which are probably caused by
  bugs in your code).
- To manually query Zulip's database interactively, use
  `./manage.py shell` or `manage.py dbshell`.
- The database(s) used for the automated tests are independent from
  the one you use for manual testing in the UI, so changes you make to
  the database manually will never affect the automated tests.

## Web

- Once the development server (`run-dev`) is running, you can visit
  <http://localhost:9991/> in your browser.
- By default, the development server homepage just shows a list of the
  users that exist on the server and you can log in as any of them by
  just clicking on a user.
  - This setup saves time for the common case where you want to test
    something other than the login process.
  - You can test the login or registration process by clicking the
    links for the normal login page.
- Most changes will take effect automatically. Details:
  - If you change CSS files, your changes will appear immediately via
    webpack hot module replacement.
  - If you change JavaScript code (`web/src`) or Handlebars
    templates (`web/templates`), the browser window will be
    reloaded automatically.
  - For Jinja2 backend templates (`templates/*`), you'll need to reload
    the browser window to see your changes.
- Any JavaScript exceptions encountered while using the web app in a
  development environment will be displayed as a large notice, so you
  don't need to watch the JavaScript console for exceptions.
- Both Chrome and Firefox have great debuggers, inspectors, and
  profilers in their built-in developer tools.
- `debug.js` has some occasionally useful JavaScript profiling code.

## Mobile

See the mobile project's documentation on [getting set up to develop
and contribute to the mobile app][mobile-development-guide].

## External access to the dev server

By default, the dev server is reachable only from the machine it
runs on: Vagrant forwards port 9991 to the host's loopback
interface, and `run-dev` listens only on `localhost` otherwise.
The most common reason to change that is **running the mobile app
against your dev server**: a phone or emulator needs an address
it can resolve, and Zulip's realm-subdomain routing has to agree
on the same address. In dev mode `EXTERNAL_HOST` drives
`REALM_HOSTS` (see `zproject/dev_settings.py`), so without setting
it, the `zulip` realm stays pinned to `localhost:9991` even after
the request reaches the box.

For installing the app, see the [mobile setup
guide][mobile-development-guide]; the [mobile dev-server
guide][mobile-dev-server-guide] is the canonical end-to-end recipe
on the mobile side. The steps below describe the dev-server-side
configuration and apply equally to a browser running on another
machine on your LAN.

:::{important}
The Zulip development environment is not hardened for exposure to
the public internet. Enable external access only for short testing
windows, and turn it off when you are done.
:::

The simplest path depends on which client you're reaching from:

- **iOS simulator (macOS).** The simulator shares its host's
  network interface, so `http://localhost:9991` works as-is — no
  configuration needed.
- **Android emulator on the same machine.** The emulator routes
  `10.0.2.2` to the host's loopback. Skip Step 1 below and run
  `EXTERNAL_HOST=10.0.2.2:9991 ./tools/run-dev`.
- **Physical device, or any other off-host client.** Follow both
  steps below.

1. **Make the dev server listen on a non-loopback address.** Find
   the host's LAN IP first; `ip route get 8.8.8.8` (Linux) prints
   it after `src`, macOS's Network preferences pane shows it, and
   `ipconfig` works on Windows. Then:

   - **Vagrant:** add `HOST_IP_ADDR 0.0.0.0` to
     `~/.zulip-vagrant-config` and run `vagrant reload` — see
     [Using a different port for Vagrant][vagrant-host-ip] for
     background. `run-dev` inside the guest already listens on all
     interfaces for the `vagrant` user, so no further change is
     needed there.
   - **Direct install on the host OS:** pass `--interface=''` to
     `run-dev` in the next step.

1. **Start `run-dev` with `EXTERNAL_HOST` set to that address.**
   For example, with the host's LAN IP at `192.168.1.10` on a
   direct install:

   ```bash
   EXTERNAL_HOST=192.168.1.10:9991 ./tools/run-dev --interface=''
   ```

   On Vagrant, drop `--interface=''`.

Sanity-check from another device on the same network:

```bash
curl -I "http://192.168.1.10:9991/login/"
```

A `200` response confirms the chain is wired up; a connection
timeout or `Connection refused` points at `HOST_IP_ADDR`,
`--interface`, or a host firewall. Then point the mobile app (or
another machine's browser) at `http://192.168.1.10:9991`.

[rest-api]: https://zulip.com/api/rest
[authentication-dev-server]: authentication.md
[django-runserver]: https://docs.djangoproject.com/en/5.0/ref/django-admin/#runserver
[new-feature-tutorial]: ../tutorials/new-feature-tutorial.md
[testing-docs]: ../testing/testing.md
[mobile-development-guide]: https://github.com/zulip/zulip-flutter/blob/main/docs/setup.md
[mobile-dev-server-guide]: https://github.com/zulip/zulip-flutter/blob/main/docs/howto/dev-server.md
[vagrant-host-ip]: setup-recommended.md#using-a-different-port-for-vagrant
