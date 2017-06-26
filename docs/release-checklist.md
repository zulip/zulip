# Zulip server release checklist

This document has reminders of things one might forget to do when
preparing a new release.

### A week before the release

* Upgrade all Python dependencies in `requirements` to latest
  upstream versions so they can burn in (use `pip list --outdated`).
* Update all the strings on Transifex and notify translators that they
  should translate the new strings to get them in for the next
  release.
* Update `changelog.md` with major changes going into the release.
* Create a burndown list of bugs that need to be fixed before we can
  release, and make sure all of them are being worked on.

### Final release preparation

* Update `changelog.md` with any final changes since the last update.
* Draft the release notes; see previous zulip-announce emails for the
  tooling needed.
* Download updated translation strings from Transifex and commit them.
* Use `build-release-tarball` to generate a release tarball.
* Test the new tarball extensively, both new install and upgrade from last
  release, on both Trusty and Xenial.
* Repeat until release is ready.

### Executing the release

* Do final updates to `changelog.md`.
* Update `ZULIP_VERSION` in `version.py`.
* Update `version` and/or `release` in `docs/conf.py` (ReadTheDocs meta tags).
* Use `build-release-tarball` to generate a final release tarball.
* Post the release tarball on zulip.org and update zulip.org.
* Create a git tag and push the tag.
* Upload the release on GitHub so it doesn't provide a broken release tarball.
* Email zulip-announce with the release notes
* For a major release, post on the blog, tweet, etc.

### Post-release

* Update `ZULIP_VERSION` in `version.py` to e.g. `1.6.0+git`.
