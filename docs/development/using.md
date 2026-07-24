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

## Accessing development environment from other systems

:::{warning}
The development environment is not hardened against hostile
traffic. Only expose it to networks you trust, and only while
testing.
:::

By default, the development environment is reachable only from the
machine it runs on. The most common reason to change that is running
the mobile app on a phone or emulator against it (the [mobile
dev-server guide][mobile-dev-server-guide] covers the client-side
setup).

First, find your host's IP address on your network:

::::{tab-set}

:::{tab-item} Windows
:sync: os-windows

Run `ipconfig` and look for the IPv4 address.
:::

:::{tab-item} macOS
:sync: os-mac

Run `ipconfig getifaddr en0`, or open the Network settings pane.
:::

:::{tab-item} Linux
:sync: os-linux

Run `ip addr` and look for your network interface's address.
:::

::::

The development server listens on port 9991. The steps below use
`192.168.1.10` as an example IP address, so the server ends up
reachable at `192.168.1.10:9991`.

1. If you're using Vagrant, [set `HOST_IP_ADDR 0.0.0.0` in
   `~/.zulip-vagrant-config`][vagrant-host-ip] and run
   `vagrant reload`, so that the VM accepts connections from other
   machines.

2. Start the development server with `EXTERNAL_HOST` set to the
   address other systems will use to reach it, so that the Zulip
   server knows what base URL it's being accessed at:

   ```bash
   env EXTERNAL_HOST=192.168.1.10:9991 ./tools/run-dev --interface=''
   ```

   `--interface=''` makes `run-dev` listen on all network
   interfaces; it's needed only outside Vagrant, since inside the
   VM `run-dev` already does this and Vagrant controls which ports
   are exposed to the network.

The development environment is now reachable from other devices on
your network at `http://192.168.1.10:9991`.

To instead let a service hosted outside your network (such as a
cloud-hosted SaaS product) reach your development environment, you
can use a tunneling tool to get a temporary public URL, and set
`EXTERNAL_HOST` to the hostname the tunnel gives you.

[rest-api]: https://zulip.com/api/rest
[authentication-dev-server]: authentication.md
[django-runserver]: https://docs.djangoproject.com/en/5.0/ref/django-admin/#runserver
[new-feature-tutorial]: ../tutorials/new-feature-tutorial.md
[testing-docs]: ../testing/testing.md
[mobile-development-guide]: https://github.com/zulip/zulip-flutter/blob/main/docs/setup.md
[mobile-dev-server-guide]: https://github.com/zulip/zulip-flutter/blob/main/docs/howto/dev-server.md
[vagrant-host-ip]: setup-recommended.md#using-a-different-port-for-vagrant
