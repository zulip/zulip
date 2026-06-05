---
orphan: true
---

# Miatsu.co release lifecycle

Operational lifecycle for the Miatsu.co fork — deploy, rollback, migrations, and
client-fork compatibility — the counterpart to Zulip's upstream
[release lifecycle](../overview/release-lifecycle.md). For _making_ fork changes,
see [the fork maintenance conventions](maintaining-the-fork.md).

## What a release is

A Miatsu.co release is a tagged commit on the fork's `main` branch — an upstream
Zulip base plus the fork's commits — identified by its `MIATSU_VERSION`
(`zerver/lib/miatsu.py`). The version pins the rest: a release merges one upstream
base and ships one capability set. The server advertises all three in
`POST /register` and `GET /server_settings`:

- `miatsu_version` — the release,
- `zulip_merge_base` — the upstream commit it merges (fixed by the release),
- `miatsu_capabilities` — the fork features it enables (fixed by the release).

A deployment chooses a `miatsu_version`; the other two follow. There is no fixed
cadence; cut a release when a change is needed in production.

## Deploying to production

The server deploys from git, from the fork repo:

1. Point the deployment at the fork once, in `/etc/zulip/zulip.conf`:

   ```ini
   [deployment]
   git_repo_url = https://github.com/BearlyBelievable/Miatsu.co.git
   ```

2. Upgrade to a branch, tag, or commit:

   ```bash
   /home/zulip/deployments/current/scripts/upgrade-zulip-from-git main
   ```

This fetches the ref into the local cache (`/srv/zulip.git`), builds a new
timestamped deployment under `/home/zulip/deployments/<YYYY-MM-DD-HH-MM-SS>/`,
rebuilds the virtualenv and assets when `PROVISION_VERSION` (`version.py`)
changed, runs database migrations, and restarts. The `current` and `last`
symlinks track the active and prior deployments. `/etc/zulip/pre-deploy.d/*.hook`
and `/etc/zulip/post-deploy.d/*.hook` scripts run around the restart with
`ZULIP_OLD_VERSION` / `ZULIP_NEW_VERSION` (and, for git deploys,
`ZULIP_OLD_MERGE_BASE_COMMIT` / `ZULIP_NEW_MERGE_BASE_COMMIT`) in the
environment — a hook point for a companion-client release step.

## Database migrations across upstream merges

Zulip numbers migrations sequentially under `zerver/migrations/` (`0802_…`,
`0803_…`), each declaring the previous one in its `dependencies`. The fork's
migrations branch from the upstream number they were written against, and the
next upstream release reuses those numbers: a merge leaves the `zerver` migration
graph with two leaf nodes (a "multiple heads" state) that Django refuses to run.

A migration's home is fixed by which model it changes. A table the fork _adds_
(its own model) goes in a separate `miatsu` Django app with its own
`miatsu/migrations/` sequence, which upstream never numbers into. A change to an
_existing_ upstream model (e.g., a new field on `Realm`) must be a `zerver`
migration, and is the only kind that hits the clash above. For each `zerver`
migration the fork carries, on each merge:

- **Re-chain onto upstream's new head.** Renumber the fork's migrations to sit
  _after_ upstream's new latest migration and re-point their `dependencies` at
  it, which restores a single linear graph. (A `makemigrations --merge` migration
  also unifies the heads without renumbering, but adds a node every merge.)
- **Reconcile already-applied migrations on production.** Renaming a migration
  production has already run leaves the old name in the `django_migrations` table,
  so Django re-runs the renamed copy and fails (the column already exists). In the
  deploy that ships the renumbering, fake-apply the renamed migrations
  (`manage.py migrate --fake zerver <new_name>`) or rename the records; verify
  with `manage.py showmigrations zerver`.

**Rollback interaction** (see [Rollback](#rollback)): rolling back _past_ a fork
migration runs older code against the newer schema. An additive column the old
code ignores is fine; a `NOT NULL` column with no `db_default` is not — the old
code can't populate it on insert (e.g., creating a realm), so that case is a
restore-from-backup, not a symlink swap.

## Rollback

Code rollback is atomic — re-run the prior deployment's restart:

```bash
/home/zulip/deployments/last/scripts/restart-server
# ...or a specific older build:
/home/zulip/deployments/2026-01-15-14-30-45/scripts/restart-server
```

A symlink swap restores _code_, not _schema_: **rollback does not reverse
database migrations.**

- A deploy with backward-compatible migrations (the prior release's code runs
  against the new schema) rolls back with the restart alone.
- A deploy with a non-backward-compatible migration needs the pre-upgrade
  database backup to roll back. Take one before a migrating deploy with
  `/home/zulip/deployments/current/manage.py backup --output=...`, and restore
  with `scripts/setup/restore-backup`.
- `check-database-compatibility` runs during every upgrade and blocks deploying
  _older_ code whose migration set is behind the live database, so an unsafe
  downgrade fails loudly instead of corrupting state.

`purge-old-deployments` runs at the end of each upgrade and retains roughly 14
days of dated deployments, which bounds how far back a code rollback can reach.
Per-release migration and upgrade specifics are recorded in the
[changelog](changelog.md).

## Coordinating companion client forks

Client forks (e.g., a Flutter app) detect fork features by **named capability**
in `miatsu_capabilities`, not by comparing `zulip_feature_level` (upstream-owned,
reused on future merges). Capability detection is what lets the server and its
clients release independently, in any order:

- A server release that **adds** a capability is backward-compatible — existing
  clients ignore the unknown flag.
- A client release that **uses** a capability guards on the flag, so it degrades
  against a server that does not advertise it.

Two consequences (see
[Capability signaling](maintaining-the-fork.md#capability-signaling) for the flag
rules):

- `DESKTOP_MINIMUM_VERSION` (`version.py`) hard-blocks older clients server-side
  and forces a client upgrade, so it applies only to a break a client cannot
  feature-detect around; additive changes use a capability flag instead.
- A change needing a non-backward-compatible protocol shift on both sides at once
  has a required deploy order. Stage it as add-new-capability → migrate clients →
  retire the old path, which keeps each side independently deployable.
