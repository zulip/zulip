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

### Final release preparation

* Download updated translation strings from Transifex and commit them.
* Use `build-release-tarball` to generate a release tarball.
* Test the new tarball extensively, both new install and upgrade from last
  release, on both Trusty and Xenial.
* Do final updates to `changelog.md`.
* Update `ZULIP_VERSION` in `version.py`.
* Repeat until release is ready.
* Draft the release notes; see previous zulip-announce emails for the
  tooling needed.

### Executing the release

* Post the release tarball on zulip.org and update zulip.org.
* Create a git tag and push the tag.
* Upload the release on GitHub so it doesn't provide a broken release tarball.
* Email zulip-announce with the release notes.
