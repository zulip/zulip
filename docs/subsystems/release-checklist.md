# Zulip server release checklist

This document has reminders of things one might forget to do when
preparing a new release.

### A week before the release

- _Major releases only (e.g., 4.0):_
  - Upgrade all Python dependencies in
    `requirements` to latest upstream versions so they can burn in (use
    `pip list --outdated`).
  - Upgrade all puppet dependencies in `puppet/deps.yaml`
  - Upgrade all puppet-installed dependencies (e.g., Smokescreen, go,
    etc) in `puppet/zulip/manifests/common.pp`
  - [Post a message to
    Weblate](https://hosted.weblate.org/projects/zulip/#announcement)
    inviting translators to translate new strings.
  - Merge draft updates to the [changelog](../overview/changelog.md)
    with changes since the last release. While doing so, take notes on
    things that might need follow-up work or documentation before we
    can happily advertise them in a release blog post.
- Create a burn-down list of issues that need to be fixed before we can
  release, and make sure all of them are being worked on.
- Draft the release blog post (a.k.a. the release notes) in Paper. In
  it, list the important changes in the release, from most to least
  notable.

### Final release preparation

- Update the Paper blog post draft with any new commits.
- Merge updated translations from Weblate (using the appropriate
  branch for the release).
- Use `build-release-tarball` to generate a pre-release tarball.
- Test the new tarball extensively, both new install and upgrade from last
  release, on Ubuntu 22.04.
- Repeat until release is ready.
- Send around the Paper blog post draft for review.
- Move the blog post draft to Astro:
  - Use "··· > Export > Markdown" to get a pretty good Markdown
    conversion, and save it in `src/posts` with a filename appropriate
    for a URL slug.
  - Add the needed YAML frontmatter.
  - Move any images into `public` and update their references.
  - Proofread, especially for formatting.
  - If the draft post should remain secret until release, avoid using
    a guessable Git branch name for the pull request (the deployment
    preview URL is based on the branch name).
- _Major releases only (e.g., 4.0):_ Schedule team members to provide
  extra responsive #production help support following the release.

### Executing the release

- Create the release commit, on `main` (for major releases) or on the
  release branch (for minor releases):
  - Copy the Markdown release notes for the release into
    `docs/overview/changelog.md`.
  - Verify the changelog passes lint, and has the right release date.
  - _Major releases only:_ Adjust the `changelog.md` heading to have
    the stable release series boilerplate.
  - Update `ZULIP_VERSION` and `LATEST_RELEASE_VERSION` in `version.py`.
  - _Major releases only:_ Update `API_FEATURE_LEVEL` to a feature
    level for the final release, and document a reserved range.
- Run `tools/release` with the release version.
- Update the [Docker image](https://github.com/zulip/docker-zulip):
  - Commit the Docker updates:
    - Update `ZULIP_GIT_REF` in `Dockerfile`
    - Update `README.md`
    - Update the image in `docker-compose.yml`, as well as the `ZULIP_GIT_REF`
  - Commit the Helm updates:
    - Add a new entry to `kubernetes/chart/zulip/CHANGELOG.md`
    - Update the `appVersion` in `kubernetes/chart/zulip/Chart.yaml`
    - Update the `tag` in `kubernetes/chart/zulip/values.yaml`
    - Update the docs by running `helm-docs`
    - Update the `image` in `kubernetes/manual/zulip-rc.yml`
  - Build the image: `docker build . -t zulip/docker-zulip:4.11-0 --no-cache`
  - Also tag it with `latest`: `docker build . -t zulip/docker-zulip:latest`
  - Push those tags: `docker push zulip/docker-zulip:4.11-0; docker push zulip/docker-zulip:latest`
  - Push the commits to `main`.
- Merge the blog post PR.
- Announce the release, pointing to the blog post, via:
  - Email to [zulip-announce](https://groups.google.com/g/zulip-announce)
  - Email to [zulip-blog-announce](https://groups.google.com/a/zulip.com/g/zulip-blog-announce)
  - Message in [#announce](https://chat.zulip.org/#narrow/channel/1-announce)
  - Tweet from [@zulip](https://twitter.com/zulip).
  - Toot from [fosstodon.org/@zulip](https://fosstodon.org/@zulip)

### Post-release

- The DigitalOcean one-click image will report in an internal channel
  once it is built, and how to test it. Verify it, then publish it to
  DigitalOcean marketplace.
- _Major releases only:_
  - Create a release branch (e.g., `4.x`).
  - On the release branch, update `ZULIP_VERSION` in `version.py` to
    the present release with a `+git` suffix, e.g., `4.0+git`.
  - On `main`, update `ZULIP_VERSION` to the future major release with
    a `-dev+git` suffix, e.g., `5.0-dev+git`. Make a Git tag for this
    update commit with a `-dev` suffix, e.g., `5.0-dev`. Push the tag
    to both zulip.git and zulip-internal.git to get a correct version
    number for future Cloud deployments.
  - Add the new release to `.github/ISSUE_TEMPLATE/2_bug_report.md`.
  - Consider removing a few old releases from the issue template and
    ReadTheDocs; we keep about two years of back-versions.
  - Update Weblate to add a component on the release branch for
    Django; then add a parallel Frontend component by using "Duplicate
    this component" on the Django release branch component.
  - In Weblate, remove the previous stable components.
  - Add a new CI production upgrade target:
    - Build a docker image: `cd tools/ci && docker build . -f Dockerfile.prod --build-arg=BASE_IMAGE=zulip/ci:bookworm --build-arg=VERSION=7.0 --tag=zulip/ci:bookworm-7.0 && docker push zulip/ci:bookworm-7.0`
    - Add a new line to the `production_upgrade` matrix in
      `.github/workflows/production-suite.yml`.
  - Update /history page in `templates/corporate/history.md`.
  - Inspect all `TODO/compatibility` comments for whether we can
    remove any backwards-compatibility code following this release.
- _Minor releases only (e.g., 3.2):_
  - On the release branch, update `ZULIP_VERSION` to the present
    release with a `+git` suffix, e.g., `3.2+git`.
  - On main, update `LATEST_RELEASE_VERSION` with the released
    version, as well as the changelog changes from the release branch.
- _Prereleases only (e.g., 7.0-beta3):_
  - Atop the prerelease commit (e.g., `7.0-beta3`), make a commit
    updating `ZULIP_VERSION` to the prerelease version with a `+git`
    suffix, e.g., `7.0-beta3+git`. Push this to `main`. (If `main` has
    already diverged from the prerelease, a merge commit will be
    needed here.)
  - Delete the prerelease branch (e.g., `7.0-beta3-branch`); it's now
    an ancestor of `main` and thus unnecessary.
