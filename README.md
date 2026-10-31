# Zulip

Zulip is an open-source team chat application built around topic-based
conversations. It supports both live chat and asynchronous communication. This
repository contains the Zulip server, web application, development tools, and
documentation.

Zulip is licensed under the Apache License 2.0; see [LICENSE](LICENSE).

## What is in this repository?

Zulip is a full-stack application. Its main server is written in Python with
Django, and its browser application is built with JavaScript and TypeScript.
The web client communicates with the server over HTTP APIs and a real-time
event system.

### Main directories

| Path | Purpose |
| --- | --- |
| `zerver/` | Main Django application: data models, views, business logic, workers, integrations, and backend tests. |
| `zproject/` | Django project configuration, URL routing, authentication, and settings. |
| `web/src/` | Browser application JavaScript and TypeScript source. |
| `web/styles/` | Web application CSS and stylesheets. |
| `web/templates/` | Handlebars templates used by the frontend. |
| `templates/` | Server-rendered Jinja templates, including pages and emails. |
| `static/` | Static assets served directly, including images. |
| `web/images/`, `web/icons/` | Frontend image and icon source assets. |
| `analytics/`, `confirmation/`, `zilencer/` | Additional Django applications for analytics, email confirmation, and server administration/development functionality. |
| `api_docs/` | REST API documentation and API reference source. |
| `docs/` | Developer, architecture, setup, and testing documentation. |
| `starlight_help/` | User-facing Zulip Help Center content. |
| `tools/` | Development, provisioning, linting, and test scripts. |
| `scripts/` | Operational and deployment scripts. |
| `puppet/` | Puppet configuration used for production deployment. |
| `locale/` | Translation files for backend and frontend. |

For a fuller map, see the [directory structure guide](docs/subsystems/directory-structure.md).

### Technology and services

- **Backend:** Python and Django, with Tornado for real-time event delivery.
- **Frontend:** JavaScript and TypeScript, Handlebars templates, and CSS. Frontend dependencies and scripts are managed with pnpm (see `package.json` and `pnpm-lock.yaml`).
- **Primary database:** PostgreSQL. Zulip uses PostgreSQL for application data and its built-in full-text search; the PGroonga extension supports additional search functionality.
- **Supporting services:** Redis is used for caching and related coordination, RabbitMQ handles internal asynchronous queues, and nginx is used in deployed environments. The development environment provisions the services required to run Zulip.

See the [architecture overview](docs/overview/architecture-overview.md),
[dependency guide](docs/subsystems/dependencies.md), and
[database architecture](docs/overview/architecture-overview.md) for details.

## Getting started as a contributor

Start with the [guide for new contributors](https://zulip.readthedocs.io/en/latest/contributing/contributing.html)
and the [development setup tutorial](docs/development/setup-recommended.md).
Zulip's recommended development setup uses WSL 2 on Windows and Vagrant with
Docker on macOS and Linux. The setup tutorial walks through prerequisites,
getting the code, provisioning services, and starting the development server.

Once your development environment is ready, common commands include:

```bash
./tools/run-dev
./tools/lint path/to/changed/files
./tools/test-backend zerver.tests.test_module
./tools/test-js-with-node
```

Run development commands in the provisioned Zulip environment. Consult the
[development setup guide](docs/development/setup-recommended.md) and
[testing documentation](docs/testing/testing.md) for current instructions,
options, and test selection guidance.

## Finding your way around the code

- Backend request routing starts in `zproject/urls.py`; most application
  endpoints and behavior live under `zerver/`.
- Django models in `zerver/models/` define application data. Database schema
  changes are managed with Django migrations.
- Frontend source is primarily under `web/src/`; templates and styles are in
  `web/templates/` and `web/styles/`.
- Backend tests are in `zerver/tests/`; frontend unit tests are in
  `web/tests/`, and browser integration tests are in `web/e2e-tests/`.
- REST API documentation is in `api_docs/` and the OpenAPI specification is
  maintained under `zerver/openapi/`.

The [directory structure guide](docs/subsystems/directory-structure.md) and
[new feature tutorial](docs/tutorials/new-feature-tutorial.md) provide more
context on how a change flows through the codebase.

## Contributing

Before opening a pull request, read [CONTRIBUTING.md](CONTRIBUTING.md),
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and the relevant development
documentation. Zulip expects contributions to include appropriate tests and to
follow the project's code style and review process.

You can also ask questions or discuss contributing in the
[Zulip development community](https://zulip.com/development-community/).

## More information

- [Zulip website](https://zulip.com/)
- [Contributor documentation](https://zulip.readthedocs.io/en/latest/contributing/contributing.html)
- [Self-hosting information](https://zulip.com/self-hosting/)
- [Security policy](SECURITY.md)
- [License](LICENSE)