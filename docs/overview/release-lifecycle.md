# Release lifecycle

This page details the release lifecycle for the Zulip server and
client-apps, well as our policies around backwards-compatibility and
security support policies. In short:

- We recommend always running the latest releases of the Zulip clients
  and servers. Server upgrades are designed to Just Work; mobile and
  desktop client apps update automatically.
- The server and client apps are backwards and forwards compatible
  across a wide range of versions. So while it's important to upgrade
  the server to get security updates, bug fixes, and new features, the
  mobile and desktop apps will continue working for at least 18 months
  if you don't do so.
- New server releases are announced via the low-traffic
  [zulip-announce email
  list](https://groups.google.com/g/zulip-announce). We
  highly recommend subscribing so that you are notified about new
  security releases.
- Zulip Cloud runs the branch that will become the next major
  server/web app release, so it is always "newer" than the latest
  stable release.

## Server and web app

The Zulip server and web app are developed together in the [Zulip
server repository][zulip-server].

### Stable releases

- Zulip Server **stable releases**, such as Zulip 4.5.
  Organizations self-hosting Zulip primarily use stable releases.
- The numbering scheme is simple: the first digit indicates the major
  release series (which we'll refer to as "4.x"). (Before Zulip 3.0,
  Zulip versions had another digit, e.g. 1.9.2 was a bug fix release
  in the Zulip 1.9.x major release series).
- [New major releases][blog-major-releases], like Zulip 4.0, are
  published every 3-6 months, and contain hundreds of features, bug
  fixes, and improvements to Zulip's internals.
- New maintenance releases, like 4.3, are published roughly once a
  month. Maintenance releases are designed to have no risky changes
  and be easy to reverse, to minimize stress for administrators. When
  upgrading to a new major release series, We recommend always
  upgrading to the latest maintenance release in that series, so that
  you use the latest version of the upgrade code.
- For the dates of past stable releases,
  [see the Zulip blog][blog-releases].

Starting with Zulip 4.0, the Zulip web app displays the current server
version in the gear menu. With older releases, the server version is
available [via the API](https://zulip.com/api/get-server-settings).

This ReadTheDocs documentation has a widget in the lower-left corner
that lets you view the documentation for other versions. Other
documentation, like our [Help Center](https://zulip.com/help/), [API
documentation](https://zulip.com/api/), and [Integrations
documentation](https://zulip.com/integrations/), are distributed with
the Zulip server itself (E.g. `https://zulip.example.com/help/`).

[blog-major-releases]: https://blog.zulip.com/tag/major-releases/
[blog-releases]: https://blog.zulip.com/tag/release-announcements/

### Git versions

Many Zulip servers run versions from Git that have not been published
in a stable release.

- [Zulip Cloud](https://zulip.com) runs the `zulip-cloud-current`
  branch; this the `main` branch, with some cherry-picked bug fixes,
  but delayed somewhat. It is usually one to two weeks behind `main`,
  depending on the complexity of recent major UI or internals changes
  that we'd like to bake longer on chat.zulip.org before exposing them
  to the full Zulip Cloud userbase.
- [chat.zulip.org][chat-zulip-org], the bleeding-edge server for the
  Zulip development community, is upgraded to `main` several times
  every week. We also often "test deploy" changes not yet in `main`
  to chat.zulip.org to facilitate design feedback.
- We maintain Git branches with names like `4.x` containing backported
  commits from `main` that we plan to include in the next maintenance
  release. Self-hosters can [upgrade][upgrade-from-git] to these
  stable release branches to get bug fixes staged for the next stable
  release (which is very useful when you reported a bug whose fix we
  choose to backport). We support these branches as though they were a
  stable release.
- Self-hosters who want new features not yet present in a major
  release can [upgrade to `main`][upgrading-to-main] or run [a fork
  of Zulip][fork-zulip].

### Compatibility and upgrading

A Zulip design goal is for there never to be a reason to run an old
version of Zulip. We work extremely hard to make sure Zulip is stable
for self-hosters, has no regressions, and that the [Zulip upgrade
process](../production/upgrade.md) Just Works.

The Zulip server and client apps are all carefully engineered to
ensure compatibility with old versions. In particular:

- The Zulip mobile and desktop apps maintain backwards-compatibility
  code to support any Zulip server version from the last 18 months.
- Zulip maintains an [API changelog](https://zulip.com/api/changelog)
  detailing all changes to the API to make it easy for client
  developers to do this correctly.
- The Zulip server preserves backwards-compatibility in its API to
  support versions of the mobile and desktop apps released in roughly
  the last year. Because these clients auto-update, generally there
  are only a handful of active clients left by the time we desupport a
  version.

As a result, we generally do not backport changes to previous stable
release series except in rare cases involving a security issue or
critical bug just after publishing a major release.

[upgrade-from-git]: ../production/upgrade.md#upgrading-from-a-git-repository

### Security releases

When we discover a security issue in Zulip, we publish a security and
bug fix release, transparently documenting the issue(s) using the
industry-standard [CVE advisory process](https://cve.mitre.org/).

When new security releases are published, we simultaneously publish
the fixes to the `main` and stable release branches (E.g. `4.x`), so
that anyone using those branches can immediately upgrade as well.

See also our [security model][security-model] documentation.

[security-model]: ../production/security-model.md

### Upgrade nag

Starting with Zulip 4.0, the Zulip web app will display a banner
warning users of a server running a Zulip release that is more than 18
months old. We do this for a few reasons:

- It is unlikely that a server of that age is not vulnerable to
  a security bug in Zulip or one of its dependencies.
- The Zulip mobile and desktop apps are only guaranteed to support
  server versions less than 18 months old.

The nag will appear only to organization administrators starting a
month before the deadline; after that, it will appear for all users on
the server.

You can adjust the deadline for your installation by setting e.g.
`SERVER_UPGRADE_NAG_DEADLINE_DAYS = 30 * 21` in
`/etc/zulip/settings.py` and then [restarting the server](../production/settings.md).

### Operating system support

For platforms we support, like Debian and Ubuntu, Zulip aims to
support all versions of the upstream operating systems that are fully
supported by the vendor. We document how to correctly [upgrade the
operating system][os-upgrade] for a Zulip server, including how to
correctly chain upgrades when the latest Zulip release no longer
supports your OS.

Note that we consider [Ubuntu interim releases][ubuntu-release-cycle],
which only have 8 months of security support, to be betas, not
releases, and do not support them in production.

[ubuntu-release-cycle]: https://ubuntu.com/about/release-cycle

### Server roadmap

The Zulip server project uses several GitHub labels to structure
communication within the project about priorities:

- The [high priority][label-high] label tags issues that we consider
  important. This label is meant to be a determination of importance
  that can be done quickly and then used as an input to planning
  processes.
- The [release goal][label-release-goal] label is used for work that
  we hope to include in the next major release. The related [post
  release][label-post-release] label is used to track work we want to
  focus on shortly after the next major release.

The Zulip community feels strongly that all the little issues are, in
aggregate, just as important as the big things. Most resolved issues
do not have any of these priority labels.

We welcome participation from our user community in influencing the Zulip
roadmap. If a bug or missing feature is causing significant pain for you, we'd
love to hear from you, either in
[chat.zulip.org](https://zulip.com/development-community/) or on the relevant
GitHub issue. Please an include an explanation of your use case: such details
can be extremely helpful in designing appropriately general solutions, and also
helps us identify cases where an existing solution can solve your problem. See
our guides for [reporting bugs](../contributing/reporting-bugs.md) and [giving
feedback](../contributing/contributing.md#user-feedback) for more details.

## Client apps

Zulip's client apps officially support all Zulip server versions (and
Git commits) released in the previous 18 months, matching the behavior
of our [upgrade nag](#upgrade-nag).

- The Zulip mobile apps release new versions from the development
  branch frequently (usually every couple weeks). Except when fixing a
  critical bug, releases are first published to our [beta
  channels][mobile-beta].

- The Zulip desktop apps are implemented in [Electron][electron], the
  browser-based desktop application framework used by essentially all
  modern chat applications. The Zulip UI in these apps is served from
  the Zulip server (and thus can vary between tabs when it is
  connected to organizations hosted by different servers).

  The desktop apps automatically update soon after each new
  release. Because Zulip's desktop apps are implemented in Electron
  and thus contain a Chromium browser, security-conscious users should
  leave automatic updates enabled or otherwise arrange to promptly
  upgrade all users after a new security release.

  New desktop app releases rarely contain new features, because the
  desktop app tab inherits its features from the Zulip server/web app.
  However, it is important to upgrade because they often contain
  important security or OS compatibility fixes from the upstream
  Chromium project.

The Zulip server supports blocking access or displaying a warning to
users attempting to access the server with extremely old or known
insecure versions of the Zulip desktop and mobile apps, with an error
message telling the user to upgrade.

## API bindings

The Zulip API bindings and related projects maintained by the Zulip
core community, like the Python and JavaScript bindings, are released
independently as needed.

[electron]: https://www.electronjs.org/
[upgrading-to-main]: ../production/modify.md#upgrading-to-main
[os-upgrade]: ../production/upgrade.md#upgrading-the-operating-system
[chat-zulip-org]: https://zulip.com/development-community/
[fork-zulip]: ../production/modify.md
[zulip-server]: https://github.com/zulip/zulip
[mobile-beta]: https://github.com/zulip/zulip-mobile#using-the-beta
[label-blocker]: https://github.com/zulip/zulip/issues?q=is%3Aissue+is%3Aopen+label%3A%22priority%3A+blocker%22
[label-high]: https://github.com/zulip/zulip/issues?q=is%3Aissue+is%3Aopen+label%3A%22priority%3A+high%22
[label-release-goal]: https://github.com/zulip/zulip/issues?q=is%3Aissue+is%3Aopen+label%3A%22release+goal%22
[label-post-release]: https://github.com/zulip/zulip/issues?q=is%3Aissue+is%3Aopen+label%3A%22post+release%22
