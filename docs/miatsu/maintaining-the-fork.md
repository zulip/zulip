---
orphan: true
---

# Maintaining the Miatsu.co fork

Miatsu.co is a **downstream fork** of [Zulip](https://github.com/zulip/zulip).
This document defines the conventions that keep the fork maintainable. For how
releases are cut, deployed, and rolled back — and how the server stays in step
with any companion client forks — see the
[release lifecycle](release-lifecycle.md).

Three mechanics of merging upstream Zulip updates shape everything below:

- **Upstream files are overwritten on merge.** `version.py`,
  `api_docs/changelog.md`, and the rest are replaced when a new Zulip release is
  merged; only files unmodified by upstream Zulip survive. Fork-owned state
  therefore lives in `zerver/lib/miatsu.py`, `docs/miatsu/`, and
  `api_docs/miatsu-changelog.md`.
- **A merge conflicts only where the fork has edited an upstream file.** A new
  fork-owned file merges without conflict; each edit to a shared upstream file is
  hand-resolved on every merge.
- **`API_FEATURE_LEVEL` belongs to upstream Zulip.** Reusing it for a fork feature
  collides with the next upstream release, so Miatsu.co advertises `miatsu_version`
  and `miatsu_capabilities` instead.

## Upstream sync model: merge

Miatsu.co absorbs upstream by **merging**, not rebasing:

```bash
git fetch upstream
git merge upstream/main      # or a specific release tag, such as upstream/12.1
```

History is preserved and no commits are rewritten, which is essential for a
deployed service. Because Miatsu.co commits interleave with upstream's in
history, every Miatsu.co commit is tagged so it stays findable across merges
(see [Commit conventions](#commit-conventions)).

On each merge:

- Take upstream's `version.py` as-is (`ZULIP_VERSION`, `API_FEATURE_LEVEL`,
  `ZULIP_MERGE_BASE`). Never hand-edit these for fork reasons.
- Re-run provisioning and the full test suite.
- Resolve conflicts in the upstream files Miatsu.co edits.

`ZULIP_MERGE_BASE` (already exposed to clients as `zulip_merge_base`) records
the upstream commit a deployment is built from, so the upstream base is always
discoverable.

## Versioning

| Constant                             | Owner          | Where                  | Updated                          |
| ------------------------------------ | -------------- | ---------------------- | -------------------------------- |
| `ZULIP_VERSION`, `API_FEATURE_LEVEL` | upstream Zulip | `version.py`           | only when merging upstream Zulip |
| `MIATSU_VERSION`                     | Miatsu.co      | `zerver/lib/miatsu.py` | when cutting a Miatsu.co release |
| `MIATSU_CAPABILITIES`                | Miatsu.co      | `zerver/lib/miatsu.py` | per feature (see below)          |

A `miatsu_version` is a self-sufficient definition of a release — a tagged commit
on the Miatsu.co repository. A deployment selects a `miatsu_version`; its
`zulip_merge_base` and `miatsu_capabilities` follow from that choice as informative
details of the release's composition rather than independent choices for deployment.
The server advertises all three at runtime (`POST /register`, `GET /server_settings`)
so a client reads the resolved base and capabilities directly.

## Capability signaling

Clients must **never** detect Miatsu.co features by comparing
`zulip_feature_level` — that integer is owned by upstream and a future merge will
reuse any value Miatsu.co might pick, silently changing its meaning. Instead,
each Miatsu.co feature gets a **named capability flag** in `MIATSU_CAPABILITIES`,
advertised as `miatsu_capabilities` in both `POST /register` and
`GET /server_settings`.

Rules:

- Add the capability name in the **same commit** that makes the feature usable
  end-to-end (not in earlier scaffolding commits), so the flag never advertises
  a feature that does not yet work.
- Capability names are stable, lower-case, snake_case strings (e.g.,
  `view_user_dms`). Once shipped, treat them as API: don't rename or remove
  without a deprecation path.

## Changelog

The fork keeps two changelogs, mirroring upstream's split by scope:

- **`api_docs/miatsu-changelog.md`** — the fork's **API changelog**, analogous
  to upstream's `api_docs/changelog.md`.
- **[`changelog.md`](changelog.md)** — the operator-facing
  **release notes / version history**, analogous to upstream's
  `docs/overview/changelog.md`.

The exhaustive record of every fork change is the commit log
(`git log --grep '^Miatsu-Change:'`), mirroring how upstream relies on its commit
log for changes it doesn't enumerate.

Do **not** edit upstream's `api_docs/changelog.md` or use
`tools/create-api-changelog` / the `api_docs/unmerged.d/ZF-*` mechanism for fork
changes — that tooling assigns upstream feature levels at upstream merge time,
which never happens for Miatsu.co.

## API documentation annotations

When a Miatsu.co change touches a documented endpoint in
`zerver/openapi/zulip.yaml`, annotate it with a **Changes** note keyed to
`miatsu_version`. Upstream's `(feature level N)` form doesn't apply — the fork
has no integer level.

When the change ships a **capability flag**, name it, so a client knows what to
check:

```
**Changes**: New in Miatsu.co 0.1; detect via the `view_user_dms` capability.
```

Otherwise, the version alone is enough:

```
**Changes**: New in Miatsu.co 0.1.
```

## Commit conventions

Every fork commit carries a `Miatsu-Change:` trailer — the single marker that
keeps fork commits greppable (`git log --grep '^Miatsu-Change:'`) once upstream
merges interleave them with upstream's own:

```
Miatsu-Change: <area or capability name>
```

The top line prefix to the commit message is the usual subsystem label: a
fork-native commit (touching only fork-owned files) uses `miatsu:`; a commit that
changes a Zulip subsystem uses that subsystem's natural prefix (e.g., `realm_settings: …`).

Otherwise, follow upstream Zulip's commit discipline — each commit is one minimal
coherent idea, passes lint and tests independently, and includes its own tests.
See:

- [Contributing guide](../../CONTRIBUTING.md)
- [Commit discipline](../contributing/commit-discipline.md)
- [Code style](../contributing/code-style.md)
