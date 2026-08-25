# Running Zulip in Docker

Zulip provides an {doc}`official Docker image <docker:index>` for
deployments that prefer to run services in containers. We recommend
using it only if your organization has a preference for deploying
this way; the Docker image moderately increases the effort required
to install, maintain, and upgrade a Zulip installation, compared with
the [standard installer](install.md).

The Docker image supports two runtimes:

- **Docker Compose** for single-host deployments. See the {doc}`Docker
Compose getting started guide <docker:how-to/compose-getting-started>`.
- **Helm charts** for Kubernetes deployments. See the {doc}`Helm
getting started guide <docker:how-to/helm-getting-started>`.

Zulip's [backup tool](export-and-import.md#backups) supports
migrating between Docker and a standard installation, so you can
change your mind later.

For configuration, secrets, networking, upgrades, and other
operational topics, see the {doc}`Docker documentation
<docker:index>` in full.
