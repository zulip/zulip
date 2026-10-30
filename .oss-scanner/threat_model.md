# Zulip threat model

## What this project does and where untrusted input enters

Zulip is a team chat server. The scan target is the `zulip/zulip` checkout at
`/src`, including its server, web client, and supporting scripts. The scanner's
Dockerfile builds a release from that checkout and installs it with local
PostgreSQL, Redis, RabbitMQ, and memcached services for offline testing.
`/root/zulip` contains the release tree; the running deployment is under
`/home/zulip/deployments/current`.

The Dockerfile borrows packaging from `zulip/docker-zulip`, checked out at
`/opt/docker-zulip`, solely to provide this test environment. That repository
is not the audit target. Do not limit application findings to Docker deployments.

Operator-supplied configuration (environment variables, mounted secrets, Helm
values, Compose files) is trusted. Operators can already run arbitrary Python
through `ZULIP_CUSTOM_SETTINGS`, so do not report "an operator can inject code
via a setting" as a vulnerability on its own. Do report cases where a value
that should be inert data gets interpreted as code, a path, a shell command or
a config directive, and where a lower-privilege party could control that value
(for example a value that is taken from a Kubernetes Secret, a ConfigMap, a
data volume restored from a backup, or an upstream service).

Treat as untrusted:

- Network clients of the container's published ports (80/443 through nginx and
  25 for incoming email), including unauthenticated users.
- Authenticated users, including realm administrators, who must not gain
  access to other realms or exceed their application permissions. Treat
  messages, uploads, API requests, incoming email, and integration payloads
  as attacker-controlled input.
- Contents of the `/data` volume that might originate from outside the
  operator (restored backups, uploaded files).
- Responses from external services (certbot/Let's Encrypt, PostgreSQL, Redis,
  RabbitMQ, memcached) where a compromised or misconfigured service should not
  be able to escalate beyond what that service legitimately controls.

## Components that matter most / least

Most important:

- The Zulip application code from `zulip/zulip`, available under `/src`:
  authentication and session handling; authorization and isolation between
  realms, users, and private conversations; message rendering and stored XSS;
  uploads and file access; API endpoints, incoming email, integrations, and
  background jobs. Look for injection, SSRF, path traversal, secret disclosure,
  and code execution across these entry points. Audit the web client as well
  as the server, especially browser-side handling of untrusted content. Findings do not need a
  packaging-specific cause to be in scope.
- Zulip's own installation, upgrade, backup, and restore scripts, including
  handling of secrets, file permissions, symlinks, and attacker-controlled data.

Less important:

- Documentation, CI configuration, changelogs, and test fixtures. Documentation
  that recommends an insecure configuration is worth a low-severity note.

## How to exercise it

- The image runs a real Zulip server with PostgreSQL, Redis, RabbitMQ and
  memcached installed locally. `zulip-start` starts them and then runs the real
  `/sbin/entrypoint.sh app:run`; Zulip then answers on `http://127.0.0.1/` for
  `Host: zulip.example.net`. `zulip-stop` stops everything.
- A realm already exists, with `admin@example.com` (realm administrator) and
  `user@example.com` (regular member), both with password `very-secret`.
  `/opt/docker-zulip/ci/test-common.sh` shows how the harness drives the API.
- Exercise application endpoints as unauthenticated clients and as users with
  different permissions. Create additional users or realms where needed to
  demonstrate unauthorized access. Include the relevant application source
  paths and a reproducer in findings, including for bugs in `zulip/zulip`.
- Use `/src` to inspect and patch the enrolled source. A source edit there does
  not automatically update the installed deployment; apply a candidate fix to
  the corresponding deployed files or rebuild the release before retesting.
- There is no network during the audit. All services needed for the local
  application are installed during the Docker build. This is a production-style
  runtime, not a provisioned development environment for the full test suite.
  Run application management commands as the `zulip` user via
  `/home/zulip/deployments/current/manage.py`.

## How we rate severity

- Critical: unauthenticated remote code execution or secret disclosure in the
  container; a way for a non-operator to obtain the secrets in
  `/etc/zulip/zulip-secrets.conf` or the database credentials.
- High: account takeover; unauthorized access to private messages or other
  realms' data; stored XSS that permits privileged actions as another user;
  injection or privilege escalation from application-controlled input.
- Medium: denial of service by an unauthenticated user; limited information
  disclosure; insecure defaults with a plausible exploitation path.
- Low: hardening suggestions, documentation that recommends an insecure setup,
  and issues requiring operator-level access that is already equivalent to
  code execution.

## Anything to leave alone

- Anything that requires the operator to already control the environment,
  `ZULIP_CUSTOM_SETTINGS`, or the host.
- Reports that only list known CVEs in third-party Python/Node dependencies
  without demonstrating a vulnerability reachable through Zulip. Vulnerable
  application use of dependencies is in scope.
- The harness's HTTP-only local serving and fixed test passwords are
  intentional for this isolated audit environment.
- Issues solely in the Docker test harness, without a vulnerability in Zulip.
- Findings against third-party base images (`ubuntu:24.04`) that are only
  CVEs in the base packages.
- Style, lint and shell-quality notes with no security impact.
