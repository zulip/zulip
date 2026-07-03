# Miatsu.co fork conventions

This is Miatsu.co's fork of Zulip. We track upstream release tags and rebase
our own features on top of each new release, rather than merging. If you're
contributing to this fork, please read this page first, as it covers the
handful of conventions that make that rebase workflow sustainable, on top of
everything in the rest of [Contributing to Zulip](contributing.md).

If you're looking for Zulip's own contribution standards, such as commit
message format, PR structure, code style, review process, those are covered
thoroughly by the rest of the `docs/contributing/` section, and we follow
them as-is. This page only covers what's different about working in this fork
specifically.

## Why this page exists

Every `git rebase` onto a new Zulip release replays our commits on top of
upstream's latest code. That only stays low-friction if our additions are
structurally invisible to upstream. If we use the same field name, same
migration number, same CSS class, etc. as upstream, then a rebase that should
have been mechanical will turn into a debugging session. Everything below
exists to try and make that kind of collision impossible.

## Naming Schemes

We prefix every identifier that this fork introduces with `miatsuco`. Examples:

- Django model fields, e.g. `miatsuco_inline_upload_preview`
- CSS classes we invent, e.g. `.miatsuco-message-media-collapsed-image`
- Settings and API parameter names (should match the underlying field name)
- `property_types` dict keys
- Internal function and attribute names, even ones with low collision risk

This keeps `grep -r miatsuco` a complete, reliable inventory of every
fork-only identifier in the code-base, which is worth more than the small
extra verbosity.

**Don't** prefix classes, fields, or functions we merely read from or extend
the behavior of, as those aren't ours to rename. Prefixing something we don't
own doesn't protect anything and just makes the diff harder to review.

## Applying Migrations

Every fork migration lives in `zerver/migrations/`. Django doesn't have a
clean way for a separate app's migration to add fields to another app's
models, so a genuinely separate migrations directory isn't practical for a
change to an *existing* upstream model (e.g. a new field on `Realm`).

A fork feature that instead adds an entirely new table of its own has no such
constraint and can use a fully separate Django app with its own migration
sequence, which never intersects `zerver`'s graph at all. We prefer that when
it's an option.

For the common case (a new field on an existing model), the convention is:

- **Filename**: `zerver/migrations/miatsuco_NNNN_description.py`, numbered
  within our own sequence, and **never renamed** once written (see the note
  about reconciliation described below).
- **Dependency**: whatever `zerver` migration is the actual current tip at
  the time of the last rebase.

**Important:** naming migrations with our own prefix does *not*, by itself,
mean the dependency can be set once and forgotten. Django's migration graph is
built purely from whichever files exist on disk and what they declare, and it
has no concept of git history. If a `miatsuco_*` migration depends on some
fixed point in `zerver`'s history, and upstream ships new `zerver` migrations
that don't depend on it (which they can't because they don't know it exists),
Django ends up with two leaf nodes in the same app's graph. This creates a
"multiple heads" state that makes it refuse to run, which is true whether the
new upstream migrations arrived via a rebase or a merge; rebasing changes
how the commits got there, not what files end up on disk.

So, **on every rebase onto a new upstream tag, re-point each `miatsuco_*`
migration's `zerver` dependency at the new actual tip.** Run
`./manage.py check_miatsuco_migrations` as part of the rebase checklist so that
it verifies this automatically and fails with the specific fix if a migration
is out of date.

This has to be a management command rather than a standalone script, as
`zerver/migrations/` contains both individually numbered pre-squash migrations
and the squashed migration that replaces them, side by side. Which one Django
treats as canonical depends on which are already applied in a *specific*
database, which is a state that a static, file-only analysis cannot correctly
resolve. However, Django's own `MigrationLoader` handles correctly via a real
connection, the same way `showmigrations` and `migrate` do.

You should **never need to fake-apply anything.** Django's applied-migration
bookkeeping (`django_migrations`) keys off filename, not content, so
re-pointing an already-applied migration's `dependencies` value is a no-op for
that bookkeeping. Renaming the file would break that (the old name stays
"applied" while Django tries to re-run the new name's operations, and fails
because the column already exists), so don't do it, even when it'd make the
numbering look tidier.

## Maintaining Upstream Files

We try to keep our fork content out of files that upstream might also edit.
Where practical, fork-specific docs and tests should get their own dedicated
files, rather than being added into a file that upstream maintains. For example:

- **User-facing docs**: Rather than adding sections into upstream help-center
  pages, the file `starlight_help/src/content/docs/miatsuco-custom-features.mdx`
  holds documentation for fork-specific settings. We link to the relevant
  upstream page where useful, rather than just editing it in place.
- **Contributor-facing docs**: This page and anything like it goes in
  `docs/contributing/`, alongside (not merged into) Zulip's own pages, and
  gets linked from `docs/contributing/index.md`'s toctree.
- **Tests**: `zerver/tests/test_miatsuco.py` holds all fork-specific tests,
  in one file rather than split per feature. If a test needs a helper
  method that already exists on an upstream test class, duplicate the
  (small, stable) helper rather than sub-classing the upstream class.
  Sub-classing would silently inherit and re-run all of *its* test methods
  too under your new class, which is easy to miss in code review.

This isn't a hard rule with no exceptions. A bug fix that changes existing
upstream function behavior inherently requires editing the file that
function lives in, and that's fine and expected. The goal is eliminating
*unnecessary* shared-file surface area, not editing zero upstream files at
any cost.

## Signaling Fork Features

The main Zulip repo has a companion mobile client, developed and released
separately from this repository. It needs a reliable way to detect whether a
given server has a particular fork-specific feature, and it can't use Zulip's
own `zulip_feature_level` for that. That integer is owned and incremented
by upstream, so any value we picked for our own purposes would eventually
collide with a future upstream feature level and silently change meaning
out from under us.

Instead, `zerver/lib/miatsuco.py` defines:

- `MIATSUCO_VERSION`: A fork-owned release independent of `ZULIP_VERSION`
- `MIATSUCO_CAPABILITIES`: A list of named string flags (one per
  fork feature) a client might need to detect.

Both are advertised alongside upstream's own version fields, in the
`POST /register` and `GET /server_settings` responses, as `miatsuco_version`
and `miatsuco_capabilities`.

Rules:

- Add a capability flag in the **same commit** that makes the corresponding
  feature usable end to end, not in an earlier scaffolding commit. The
  flag should never advertise a feature that doesn't actually work yet.
- Capability names are stable, lower-case, `snake_case` strings. Once
  shipped, treat one as public API: a client may already be checking for
  it, so don't rename or remove it without a deprecation path.
- A client should check for the specific capability it needs, not infer
  feature availability from `miatsuco_version` alone. That would require
  the client to maintain its own version-to-feature mapping, which is
  exactly the coupling this mechanism exists to avoid.

## Pull Requests

In addition to Zulip's own [review guide](review-process.md):

1. Confirm your branch applies cleanly against the current base release tag
   on its own.
2. If your change is meant to be independent of other in-flight fork
   features, verify it applies correctly in either order relative to them,
   and that the resulting tree is identical either way
   (`git apply patch-a; git apply patch-b` vs. the reverse order, then
   `diff -rq`). If your change has a genuine, intentional dependency on
   another fork feature, confirm it fails *clearly and immediately* without
   that dependency present, a change that silently partially applies is
   worse than one that visibly refuses to.
3. Run `./manage.py check_miatsuco_migrations` if you've touched a migration.
4. Run the actual test suite. A clean `git apply` or `git rebase` only
   means the text merged, it isn't evidence the feature still behaves
   correctly, especially for anything client-side that unit tests don't
   reach.

## Questions

If something here is unclear, or you've hit a case this page doesn't cover, then
that's a documentation bug. Please raise it rather than guessing, as this page
is expected to evolve. If a convention here turns out to be wrong, we want to
fix the convention and this page together, in the same commit.
