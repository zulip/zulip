---
paths:
  - "zerver/openapi/**"
  - "api_docs/**"
---

# Documenting API Changes

API changes must be documented fully using our double-entry changelog
system. When starting an API change, reread `docs/documentation/api.md`
to review the process for documenting an API change. Run
`tools/create-api-changelog`; it generates an empty
`api_docs/unmerged.d/ZF-XXXXXX.md` file (where `XXXXXX` is a random
hex string the tool picks for you) and stages it for you. Document
the changes in that file as an unordered list (`*` bullets) of the
additions or changes, formatted to match `api_docs/changelog.md`.
Don't add a `**Feature level**` heading; the merge tooling emits that
itself.

In the OpenAPI yaml (`zerver/openapi/zulip.yaml`), reference the same
filename stem in **Changes** notes, e.g.,
`**Changes**: New in Zulip 13.0 (feature level ZF-XXXXXX).` The merge
process matches the `Zulip <version> (feature level ZF-XXXXXX)` shape
and overwrites both the version and the placeholder with the real
release version and final feature level. Use the upcoming release's
version — the next major release after the latest one shipped (e.g.,
13.0 while 12.0 is the current release), which you can read from the
first `## Changes in Zulip X.Y` heading in `api_docs/changelog.md`.
You must keep the literal `New in Zulip X.Y` format, or the merge
tooling won't recognize the note and CI (`check-feature-level-updated`)
will fail with the `ZF-` placeholder still in the file. Never update
`API_FEATURE_LEVEL` manually.
