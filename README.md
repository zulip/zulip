# MiAtSu.Co's fork of Zulip

This is MiAtSu.Co's fork of [Zulip](https://zulip.com), an open-source
organized team chat app. It tracks upstream Zulip releases and rebases a
small number of fork-specific features on top of each one. See
[`docs/contributing/miatsuco-fork-conventions.md`](https://github.com/BearlyBelievable/Miatsu.co/blob/main/docs/contributing/miatsuco-fork-conventions.md)
for how this fork is organized and why.

**Contributing to this fork?** Read
[`docs/contributing/miatsuco-fork-conventions.md`](https://github.com/BearlyBelievable/Miatsu.co/blob/main/docs/contributing/miatsuco-fork-conventions.md)
first. It covers the handful of things specific to this fork — naming
conventions, migration conventions, how we signal fork-specific features to
our companion mobile client, and how we structure PRs — layered on top of
upstream Zulip's own contributing documentation.

**For everything else** — setting up a development environment, code
style, commit discipline, the review process, and so on — follow [upstream
Zulip's contributing
guide](https://zulip.readthedocs.io/en/latest/contributing/contributing.html)
as-is. This fork doesn't duplicate or maintain a parallel copy of that
documentation; our conventions page above only covers what's actually
different here, and defers to upstream for the rest.

The badges, CI status, and community links in upstream Zulip's own README
(below, and at [github.com/zulip/zulip](https://github.com/zulip/zulip))
reflect upstream's project, not this fork specifically — this fork doesn't
maintain separate infrastructure for those. The two badges kept below
describe code-style tooling this fork continues to use, so they stay
accurate regardless of who maintains the fork.

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![code style: prettier](https://img.shields.io/badge/code_style-prettier-ff69b4.svg)](https://github.com/prettier/prettier)

---

[Zulip](https://zulip.com) is an open-source organized team chat app with unique
[topic-based threading][why-zulip] that combines the best of email and chat to
make remote work productive and delightful. Fortune 500 companies, [leading open
source projects][rust-case-study], and thousands of other organizations use
Zulip every day. Zulip is the only [modern team chat app][features] that is
designed for both live and asynchronous conversations.

Upstream Zulip is built by a distributed community of developers from all
around the world, with 99+ people who have each contributed 100+ commits. With
over 1,500 contributors merging over 500 commits a month, Zulip is the
largest and fastest growing open source team chat project. (These figures
describe the upstream project this fork is based on, not this fork
specifically.)

Come find us on the [development community chat](https://zulip.com/development-community/)!

[why-zulip]: https://zulip.com/why-zulip/
[rust-case-study]: https://zulip.com/case-studies/rust/
[features]: https://zulip.com/features/

## Getting started

- **Contributing to this fork**. Read
  [`docs/contributing/miatsuco-fork-conventions.md`](https://github.com/BearlyBelievable/Miatsu.co/blob/main/docs/contributing/miatsuco-fork-conventions.md)
  first, then follow upstream Zulip's [guide for new
  contributors](https://zulip.readthedocs.io/en/latest/contributing/contributing.html)
  for everything general. Upstream has invested in making Zulip's code highly
  readable, thoughtfully tested, and easy to modify, with an extraordinary
  185K words of documentation for contributors — we rely on that documentation
  rather than duplicating it.

- **Contributing non-code**. [Report an
  issue](https://zulip.readthedocs.io/en/latest/contributing/reporting-bugs.html),
  [translate](https://zulip.readthedocs.io/en/latest/translating/translating.html)
  Zulip into your language, or [give us
  feedback](https://zulip.readthedocs.io/en/latest/contributing/suggesting-features.html)
  — upstream, since these apply to Zulip generally rather than to anything
  fork-specific.

- **Checking Zulip out**. The best way to see Zulip in action is to [drop
  by](https://chat.zulip.org/?show_try_zulip_modal) the Zulip development
  community (no account required). We also recommend reading about Zulip's
  [unique approach](https://zulip.com/why-zulip/) to organizing conversations.

- **Running a Zulip server**. Upstream Zulip can be self-hosted directly on
  Ubuntu or Debian Linux, in [Docker](https://github.com/zulip/docker-zulip),
  or with prebuilt images for [Digital
  Ocean](https://marketplace.digitalocean.com/apps/zulip) and
  [Render](https://render.com/docs/deploy-zulip). Learn more about
  [self-hosting Zulip](https://zulip.com/self-hosting/). This fork doesn't
  maintain separate self-hosting documentation beyond
  [`docs/contributing/miatsuco-fork-conventions.md`](https://github.com/BearlyBelievable/Miatsu.co/blob/main/docs/contributing/miatsuco-fork-conventions.md).

- **Using Zulip without setting up a server**. Learn about [Zulip
  Cloud](https://zulip.com/zulip-cloud/) hosting options. Zulip sponsors free [Zulip
  Cloud Standard](https://zulip.com/plans/) for hundreds of worthy
  organizations, including [fellow open-source
  projects](https://zulip.com/for/open-source/).

- **Participating in [outreach
  programs](https://zulip.readthedocs.io/en/latest/contributing/contributing.html#outreach-programs)**
  like [Google Summer of Code](https://developers.google.com/open-source/gsoc/),
  through upstream Zulip.

- **Supporting Zulip**. Learn about all the ways you can [support
  Zulip](https://zulip.com/help/support-zulip-project), including contributing
  financially, and helping others discover it.

You may also be interested in reading upstream's [blog](https://blog.zulip.org/), and
following upstream on [LinkedIn](https://www.linkedin.com/company/zulip-project/),
[Mastodon](https://fosstodon.org/@zulip), and [X](https://x.com/zulip).

Zulip, and this fork, are distributed under the
[Apache 2.0](https://github.com/zulip/zulip/blob/main/LICENSE) license.
