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

[rest-api]: https://zulip.com/api/rest
[authentication-dev-server]: authentication.md
[django-runserver]: https://docs.djangoproject.com/en/5.0/ref/django-admin/#runserver
[new-feature-tutorial]: ../tutorials/new-feature-tutorial.md
[testing-docs]: ../testing/testing.md
[mobile-development-guide]: https://github.com/zulip/zulip-flutter/blob/main/docs/setup.md


## Exposing the development environment for testing integrations

Zulip provides an excellent integrations development panel for testing webhooks locally. However, some external services (for example, GitHub, Jira, or GitLab) need to send HTTP requests directly to Zulip. To test these integrations end-to-end, your local Zulip development server must be reachable outside the VM — and in many cases, from the public internet.

This section explains how to expose a local Zulip development environment and describes alternative approaches if direct exposure is not possible.

## Why this is needed

By default, the Vagrant-based Zulip development environment is only accessible from the host machine. External services cannot reach it because:

The VM only listens on 127.0.0.1 (localhost).
Webhook providers require a reachable URL to deliver events.
Many services cannot send webhooks to private IP addresses.
Exposing the development server allows you to:
Receive real webhook payloads from external services
Debug integrations in a realistic environment.

### Allow the Vagrant VM to accept external connections

Edit `zulip/Vagrantfile` and change:
  `host_ip_addr = "127.0.0.1`
to:
  `host_ip_addr = "0.0.0.0"`

This allows the Zulip development server running inside the VM to listen on all network interfaces instead of only localhost.
After making this change, reload the VM:
`vagrant reload`
### Configure the external host
Set the `EXTERNAL_HOST` environment variable so Zulip generates webhook URLs using an externally reachable address:
  `export EXTERNAL_HOST="<IP_OF_HOST>:9991"`
Alternatively, prefix the development server command:
  `EXTERNAL_HOST="<IP_OF_HOST>:9991" ./tools/run-dev.py`
### Start the development server
Run the development server with external interfaces enabled:
  `./tools/run-dev.py --interfaces=''`
At this point, the server should be reachable from outside the VM using the value of EXTERNAL_HOST.
 You will need a publicly reachable address, typically provided by a tunneling or proxy tool.
## Using a tunneling or proxy tool
 
A tunneling or proxy tool (such as Cloudflare Tunnel, ngrok, or similar services) can be used to expose the local Zulip development server through a publicly reachable HTTPS URL. This is the most reliable way to send webhooks from cloud-based services.

---

## What a tunneling or proxy tool does

- A tunneling or proxy tool will:
 - Expose your local Zulip development server (typically running on `localhost:9991`)
 - Provide a publicly reachable HTTPS URL
 - Forward incoming requests from the public internet to your local machine
 - Allow external services to send webhooks without requiring a public IP address or router configuration

---

- Install a tunneling or proxy tool
 - Choose and install a tunneling or proxy tool on your host machine. Common options include Cloudflare Tunnel, ngrok, and similar services.Verify that the tool is installed by running its version or help command.


 - Inside the Vagrant VM, start the Zulip development server by
 (`./tools/run-dev.py`).Confirm that the server is reachable from your host machine by opening the following URL in a browser:`http://localhost:9991`
 
 - Start the tunnel or proxy
 On your host machine, start the tunneling or proxy tool and configure it to forward traffic to the local Zulip development server:`http://localhost:9991`The tool will provide a publicly reachable HTTPS URL. This URL will forward incoming requests to your local Zulip server.
 
 - Configure the webhook URL
 Use the public HTTPS URL provided by the tunneling or proxy tool when configuring the webhook in the external service.
 For example, the webhook URL will typically look like:
 `https://<public-hostname>/api/v1/external/<integration-name>`

 - Successful webhook requests should appear.

