# MiAtSu.Co fork conventions

This is MiAtSu.Co's fork of Zulip. We track upstream release tags and rebase
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

## Contributing a feature

The short version of the workflow:

1. Get the latest `main` and branch off it: `git fetch origin && git checkout
main && git checkout -b my-feature`.
2. Build the feature on that branch, following the naming, migration, and
   upstream-file conventions below. Keep it to one feature per branch so it
   can be reviewed and rebased on its own.
3. Add tests for it, in a feature-named module (see Passing CI), and run the
   backend and frontend suites plus `./tools/lint -m` locally.
4. Push the branch and open a PR against `main`. CI must be green; see the
   Pull Requests and Passing CI sections for what reviewers look for.

That's it. The sections below explain the conventions those steps refer to;
read them before your first contribution, but you won't need to re-read them
every time.

## Naming Schemes

We prefix every identifier that this fork introduces with `miatsuco`. Examples:

- Django model fields, e.g., `miatsuco_inline_upload_preview`
- CSS classes we invent, e.g., `.miatsuco-message-media-collapsed-image`
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
change to an _existing_ upstream model (e.g., a new field on `Realm`).

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

**Important:** naming migrations with our own prefix does _not_, by itself,
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
treats as canonical depends on which are already applied in a _specific_
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
- **Tests**: each fork feature gets its own test module named for the
  feature, `zerver/tests/test_miatsuco_<feature>.py` (e.g.,
  `test_miatsuco_upload_preview.py`, `test_miatsuco_ogg_audio.py`). Do
  _not_ put multiple features' tests in a single shared file: because each
  feature is developed on its own branch and PR'd independently, two
  features appending to one shared test file would conflict every time
  their branches are combined. One file per feature means each branch's
  tests apply cleanly and independently, in any order.
  Shared test helpers live in `zerver/lib/test_miatsuco.py` (the
  `MiatsucoMarkdownTestMixin` class), following upstream's own convention
  of keeping reusable test base classes in `zerver/lib/` rather than in
  the test modules (the backend test runner only discovers modules under
  `zerver/tests/`, so a helper module in `zerver/lib/` is never mistaken
  for a test module). Each feature's test module imports that mixin. If
  you need a helper that already exists on an upstream test class, add it
  to the shared mixin (or duplicate the small, stable helper) rather than
  sub-classing the upstream class directly -- sub-classing would silently
  inherit and re-run all of _its_ test methods under your new class, which
  is easy to miss in code review.

This isn't a hard rule with no exceptions. A bug fix that changes existing
upstream function behavior inherently requires editing the file that
function lives in, and that's fine and expected. The goal is eliminating
_unnecessary_ shared-file surface area, not editing zero upstream files at
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

A capability flag only does something once a client reads
`miatsuco_capabilities` to gate its own behavior. The server itself does not
change behavior based on the list, it only advertises it. This fork does not
yet ship a client that consumes capabilities (upstream's mobile client has no
knowledge of fork features, and a fork-specific client is not currently
planned), so `MIATSUCO_CAPABILITIES` is intentionally empty for now, and
features ship without a flag. The rules below apply once a consuming client
exists: at that point, each fork feature a client needs to detect should
register a flag, added retroactively for existing features and in the
feature's own commit for new ones.

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

## Releases

`MIATSUCO_VERSION` (in `zerver/lib/miatsuco.py`) is this fork's own release
number, independent of `ZULIP_VERSION`. A release is a known-good snapshot:
a tag where `main` was at a specific upstream base plus a specific set of
features, CI was green, and the result actually ran on the server. Because
it is advertised to clients as `miatsuco_version`, only tag a release for a
state that has actually been deployed and verified, not merely merged.

Cut a release when a meaningful change has landed on the server and been
confirmed working, not on every merge to `main`. Bundling several features
into one release is fine and usually better than a release per feature.
Doc-only changes, tooling tweaks, and the small commits between deployments
do not need a version bump.

The number is `MAJOR.MINOR.PATCH`, with fork-specific meanings:

- **Major**: a stable-substrate milestone or a break to something promised
  as public API (removing or renaming a `MIATSUCO_CAPABILITIES` flag). The
  rebase onto the upstream 13.0 stable tag, which moves the fork off its
  volatile bridge base, is the planned 1.0.0.
- **Minor**: a new fork feature shipped and deployed, or a new capability
  flag added. This is the common bump.
- **Patch**: bug fixes to existing fork features, with no new feature and no
  new capability.

Between releases, `main` carries a `-dev` suffix (e.g., `0.2-dev`) so the
running version always shows whether it is a tagged release or somewhere
after one. Right after cutting a release, bump `main` to the next `-dev`.

The current plan: the features on the bridge base ship as `0.1`, further
features increment the minor (`0.2`, and so on), and the 13.0 rebase is
`1.0.0`.

The version is for humans (what is running, what to roll back to) and is
deliberately not load-bearing for feature detection. Clients detect
features through `MIATSUCO_CAPABILITIES`, not by comparing
`miatsuco_version` (see Signaling Fork Features above), so the release
cadence can follow whatever is meaningful to maintainers without risk of
breaking a client.

## Pull Requests

In addition to Zulip's own [review guide](review-process.md):

1. Confirm your branch applies cleanly against the current base release tag
   on its own.
2. If your change is meant to be independent of other in-flight fork
   features, verify it applies correctly in either order relative to them,
   and that the resulting tree is identical either way
   (`git apply patch-a; git apply patch-b` vs. the reverse order, then
   `diff -rq`). If your change has a genuine, intentional dependency on
   another fork feature, confirm it fails _clearly and immediately_ without
   that dependency present, a change that silently partially applies is
   worse than one that visibly refuses to.
3. Run `./manage.py check_miatsuco_migrations` if you've touched a migration.
4. Run the actual test suite. A clean `git apply` or `git rebase` only
   means the text merged, it isn't evidence the feature still behaves
   correctly, especially for anything client-side that unit tests don't
   reach.

## Passing CI

Most of what CI enforces is upstream Zulip's own tooling, and upstream
already documents it well. This fork does not restate that; read those pages
and run the same commands. In particular:

- [Linters](../testing/linters.md) covers Ruff, Prettier, and the custom
  source checks (trailing whitespace, the `e.g.,` comma rule, and so on).
  Before you push, run `./tools/lint -m` to lint just your modified files,
  and `./tools/lint --fix` to autofix what can be autofixed. `--verbose`
  explains how to fix errors that can't.
  One surprise worth knowing: a bare `./tools/lint` also runs `gitlint`,
  which checks your commit _messages_ (not just code) against `.gitlint`,
  most notably that the title is capitalized and ends with a period. CI
  skips this check (it is run with `--skip=gitlint` because it is flaky),
  so it never fails your PR, but it can fail a local full lint run in a way
  that looks unrelated to your changes. Follow Zulip's
  [commit discipline](commit-discipline.md) for message style regardless;
  it is good practice even though CI does not enforce it.
- [Testing with Django](../testing/testing-with-django.md) covers the
  backend suite and the 100% line-coverage requirement, including
  `test-backend --coverage` and the `# nocoverage` pragma.
- [Continuous integration](../testing/continuous-integration.md) covers
  how the CI jobs themselves are structured.

Fork test files are discovered automatically, with no registration step.
The backend runner collects every `zerver/tests/test_*.py`, so a feature's
`zerver/tests/test_miatsuco_<feature>.py` runs as part of the normal backend
suite. The frontend runner collects every `web/tests/*.test.cjs`, so a
`web/tests/miatsuco_<feature>.test.cjs` runs the same way. You do not add
these to any list.

On top of that upstream tooling, a couple of failure modes are specific to
maintaining this fork, and are easy to trip because upstream's own files
happen not to hit them:

- **A shared helper module that ships before the tests that use it needs
  `# nocoverage`.** `zerver/lib/test_miatsuco.py` is a helper mixin with no
  tests of its own, and coverage is enforced across `zerver/` including
  `zerver/lib/`. Until a feature's test module actually calls its helpers,
  those lines are uncovered and fail the coverage gate, so the file is
  marked `# nocoverage`. For the whole-file exclusion to apply, the very
  first line must be _exactly_ `# nocoverage` with nothing after it (see
  `tools/coveragerc`), a marker with a trailing explanation on the same
  line only excludes that one line. Once feature tests exercise every
  helper, the marker can be dropped so the helpers are held to real
  coverage through their callers.
- **`check_miatsuco_migrations` is fork-only, but it is wired into CI.**
  It runs from `tools/test-migrations` (alongside upstream's own migration
  consistency checks), so a `miatsuco_*` migration left pointing at a stale
  zerver tip fails CI rather than slipping through. Run
  `./manage.py check_miatsuco_migrations` locally if you have touched a
  migration, as covered under Applying Migrations above.

A green `git apply` or `git rebase` only means the text merged. It is not
evidence that lint, coverage, the docs build, or the tests still pass, so
run the checks above locally rather than relying on a clean apply.

## Questions

If something here is unclear, or you've hit a case this page doesn't cover, then
that's a documentation bug. Please raise it rather than guessing, as this page
is expected to evolve. If a convention here turns out to be wrong, we want to
fix the convention and this page together, in the same commit.
