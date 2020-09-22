# Zulip server release checklist

This document has reminders of things one might forget to do when
preparing a new release.

### A week before the release

* For a major release (e.g. 4.0):
  * Upgrade all Python dependencies in
    `requirements` to latest upstream versions so they can burn in (use
    `pip list --outdated`).
  * Update all the strings on Transifex and
    notify translators that they should translate the new strings to get
    them in for the next release.
* Create a burn-down list of bugs that need to be fixed before we can
  release, and make sure all of them are being worked on.
* Draft the release blog post (a.k.a. the release notes) in Paper.  In
  it, list the important changes in the release, from most to least
  notable.

### Final release preparation

* Update the Paper blog post draft with any new commits.
* _Except minor releases:_ Download updated translation strings from
  Transifex and commit them.
* Use `build-release-tarball` to generate a release tarball.
* Test the new tarball extensively, both new install and upgrade from last
  release, on both Bionic and Focal.
* Repeat until release is ready.
* Send around the Paper blog post draft for review.
* Move the blog post draft to Ghost.  (For a draft in Dropbox Paper,
  use "··· > Export > Markdown" to get a pretty good markup
  conversion.)  Proofread the post, especially for formatting.  Tag
  the post with "Release announcements" in Ghost.

### Executing the release

* Create the release commit, on master (for major releases) or on the
  release branch (for minor releases):
  * Copy the Markdown release notes for the release into
    `docs/overview/changelog.md`.
  * Update `ZULIP_VERSION` and `LATEST_RELEASE_VERSION` in `version.py`.
  * _Except minor releases:_ Update `API_FEATURE_LEVEL` to a feature
    level for the final release, and document a reserved range.
* Tag that commit with an unsigned Git tag named the release number.
* Use `build-release-tarball` to generate a final release tarball.
* Push the tag and release commit.
* Copy the tarball to `zulip.org`, and run
  `/etc/zulip/ship-release.sh` on it; this will put it in place,
  update the latest symlink, and update the SHA256 sums.
* Post the release by [editing the latest tag on
  GitHub](https://github.com/zulip/zulip/tags); use the text from
  `changelog.md` for the release notes.
* Update the [Docker image](https://github.com/zulip/docker-zulip) and
  do a release of that.
* Update the image of DigitalOcean one click app using
  [Fabric](https://github.com/zulip/marketplace-partners) and publish
  it to DO marketplace.
* Publish the blog post; check the box to "send by email."
* Email [zulip-announce](https://groups.google.com/g/zulip-announce),
  post to [#announce](https://chat.zulip.org/#narrow/stream/1-announce),
  and [send a tweet](https://twitter.com/zulip).

### Post-release

* Following a major release (e.g. 4.0):
  * Create a release branch (e.g. `4.x`).
  * On the release branch, update `ZULIP_VERSION` in `version.py` to
    the present release with a `+git` suffix, e.g. `4.0+git`.
  * On master, update `ZULIP_VERSION` to the future major release with
    a `-dev+git` suffix, e.g. `5.0-dev+git`.  Make a Git tag for this
    update commit with a `-dev` suffix, e.g. `5.0-dev`.
* Following a minor release (e.g. 3.2):
  * On the release branch, update `ZULIP_VERSION` to the present
    release with a `+git` suffix, e.g. `3.2+git`.
  * Cherry-pick the changelog changes back to `master`.
* Consider removing a few old releases from ReadTheDocs; we keep about
  two years of back-versions.
