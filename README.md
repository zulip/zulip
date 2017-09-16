**[Zulip overview](#zulip-overview)** |
**[Community](#community)** |
**[Installing for dev](#installing-the-zulip-development-environment)** |
**[Installing for production](#running-zulip-in-production)** |
**[Ways to contribute](#ways-to-contribute)** |
**[How to get involved](#how-to-get-involved-with-contributing-to-zulip)** |
**[License](#license)**

# Zulip overview

Zulip is a powerful, open source group chat application. Written in
Python and using the Django framework, Zulip supports both private
messaging and group chats via conversation streams.

Zulip also supports fast search, drag-and-drop file uploads, image
previews, group private messages, audible notifications,
missed-message emails, desktop apps, and much more.

Further information on the Zulip project and its features can be found
at <https://www.zulip.org>.

[![Build Status](https://travis-ci.org/zulip/zulip.svg?branch=master)](https://travis-ci.org/zulip/zulip) [![Coverage Status](https://img.shields.io/codecov/c/github/zulip/zulip.svg)](https://codecov.io/gh/zulip/zulip) [![Mypy coverage](https://img.shields.io/badge/mypy-100%25-green.svg)](http://blog.zulip.org/2016/10/13/static-types-in-python-oh-mypy/) [![docs](https://readthedocs.org/projects/zulip/badge/?version=latest)](http://zulip.readthedocs.io/en/latest/) [![Zulip chat](https://img.shields.io/badge/zulip-join_chat-brightgreen.svg)](https://chat.zulip.org) [![Twitter](https://img.shields.io/badge/twitter-@zulip-blue.svg?style=flat)](http://twitter.com/zulip)

## Community

There are several places online where folks discuss Zulip.

* The primary place is the
  [Zulip development community Zulip server][czo-doc] at
  chat.zulip.org.

* For Google Summer of Code students and applicants, we have
[a mailing list](https://groups.google.com/forum/#!forum/zulip-gsoc)
for help, questions, and announcements.  But it's often simpler to
[visit chat.zulip.org][czo-doc] instead.

* We have a [public development discussion mailing list][zulip-devel],
zulip-devel, which is currently pretty low traffic because most
discussions happen in our public Zulip instance.  We use it to
announce Zulip developer community gatherings and ask for feedback on
major technical or design decisions.  It has several hundred
subscribers, so you can use it to ask questions about features or
possible bugs, but please don't use it ask for generic help getting
started as a contributor (e.g. because you want to do Google Summer of
Code).  The rest of this page covers how to get involved in the Zulip
project in detail.

* Zulip also has a [blog](https://blog.zulip.org/) and
  [twitter account](https://twitter.com/zulip).

* Last but not least, we use [GitHub](https://github.com/zulip/zulip)
to track Zulip-related issues (and store our code, of course).
Anybody with a GitHub account should be able to create Issues there
pertaining to bugs or enhancement requests.  We also use Pull Requests
as our primary mechanism to receive code contributions.

The Zulip community has a [Code of Conduct][code-of-conduct].

[zulip-devel]: https://groups.google.com/forum/#!forum/zulip-devel

## Installing the Zulip Development environment

The Zulip development environment is the recommended option for folks
interested in trying out Zulip, since it is very easy to install.
This is documented in [the developer installation guide][dev-install].

## Running Zulip in production

Zulip in production supports Ubuntu 14.04 Trusty and Ubuntu 16.04
Xenial. We're happy to support work to enable Zulip to run on
additional platforms. The installation process is
[documented here](https://zulip.readthedocs.io/en/latest/prod.html).

## Ways to contribute

Zulip welcomes all forms of contributions!  This page documents the
Zulip development process.

* **Pull requests**. Before a pull request can be merged, you need to
sign the [Dropbox Contributor License Agreement][cla].  Also,
please skim our [commit message style guidelines][doc-commit-style].
We encourage early pull requests for work in progress. Prefix the title
of your pull request with `[WIP]` and reference it when asking for
community feedback. When you are ready for final review, remove
the `[WIP]`.

* **Testing**. The Zulip automated tests all run automatically when
you submit a pull request, but you can also run them all in your
development environment following the instructions in the [testing
docs][doc-test]. You can also try out [our new desktop
client][electron], which is in alpha; we'd appreciate testing and
[feedback](https://github.com/zulip/zulip-electron/issues/new).

* **Developer Documentation**.  Zulip has a growing collection of
developer documentation on [Read The Docs][doc].  Recommended reading
for new contributors includes the [directory structure][doc-dirstruct]
and [new feature tutorial][doc-newfeat]. You can also improve
[Zulip.org][z-org].

* **Mailing lists and bug tracker**. Zulip has a [development
discussion mailing list](#community) and uses [GitHub issues
][gh-issues].  There are also lists for the [Android][email-android]
and [iOS][email-ios] apps.  Feel free to send any questions or
suggestions of areas where you'd love to see more documentation to the
relevant list! Check out our [bug report guidelines][bug-report]
before submitting. Please report any security issues you discover to
zulip-security@googlegroups.com.

* **App codebases**. This repository is for the Zulip server and web
app (including most integrations).  The
[beta React Native mobile app][mobile], [Java Android app][Android]
(see [our mobile strategy][mobile-strategy]),
[new Electron desktop app][electron], and
[legacy Qt-based desktop app][desktop] are all separate repositories.

* **Glue code**. We maintain a [Hubot adapter][hubot-adapter] and several
integrations ([Phabricator][phab], [Jenkins][], [Puppet][], [Redmine][],
and [Trello][]), plus [node.js API bindings][node], an [isomorphic
 JavaScript library][zulip-js], and a [full-text search PostgreSQL
 extension][tsearch], as separate repos.

* **Translations**.  Zulip is in the process of being translated into
10+ languages, and we love contributions to our translations.  See our
[translating documentation][transifex] if you're interested in
contributing!

* **Code Reviews**. Zulip is all about community and helping each
other out.  Check out [#code review][code-review] on
[chat.zulip.org][czo-doc] to help review PRs and give comments on
other people's work. Everyone is welcome to participate, even those
new to Zulip! Even just checking out the code, manually testing it,
and posting on whether or not it worked is valuable.

[cla]: https://opensource.dropbox.com/cla/
[code-of-conduct]: https://zulip.readthedocs.io/en/latest/code-of-conduct.html
[dev-install]: https://zulip.readthedocs.io/en/latest/dev-overview.html
[doc]: https://zulip.readthedocs.io/
[doc-commit-style]: http://zulip.readthedocs.io/en/latest/version-control.html#commit-messages
[doc-dirstruct]: http://zulip.readthedocs.io/en/latest/directory-structure.html
[doc-newfeat]: http://zulip.readthedocs.io/en/latest/new-feature-tutorial.html
[doc-test]: http://zulip.readthedocs.io/en/latest/testing.html
[electron]: https://github.com/zulip/zulip-electron
[gh-issues]: https://github.com/zulip/zulip/issues
[desktop]: https://github.com/zulip/zulip-desktop
[android]: https://github.com/zulip/zulip-android
[mobile]: https://github.com/zulip/zulip-mobile
[mobile-strategy]: https://github.com/zulip/zulip-android/blob/master/android-strategy.md
[email-android]: https://groups.google.com/forum/#!forum/zulip-android
[email-ios]: https://groups.google.com/forum/#!forum/zulip-ios
[hubot-adapter]: https://github.com/zulip/hubot-zulip
[jenkins]: https://github.com/zulip/zulip-jenkins-plugin
[node]: https://github.com/zulip/zulip-node
[zulip-js]: https://github.com/zulip/zulip-js
[phab]: https://github.com/zulip/phabricator-to-zulip
[puppet]: https://github.com/matthewbarr/puppet-zulip
[redmine]: https://github.com/zulip/zulip-redmine-plugin
[trello]: https://github.com/zulip/trello-to-zulip
[tsearch]: https://github.com/zulip/tsearch_extras
[transifex]: https://zulip.readthedocs.io/en/latest/translating.html#testing-translations
[z-org]: https://github.com/zulip/zulip.github.io
[code-review]: https://chat.zulip.org/#narrow/stream/code.20review
[bug-report]: http://zulip.readthedocs.io/en/latest/bug-reports.html

## Google Summer of Code

We participated in
[GSoC](https://developers.google.com/open-source/gsoc/) in 2016 (with
[great results](https://blog.zulip.org/2016/10/13/static-types-in-python-oh-mypy/))
and [are participating](https://github.com/zulip/zulip.github.io/blob/master/gsoc-ideas.md)
in 2017 as well.

## How to get involved with contributing to Zulip

First, subscribe to the Zulip [development discussion mailing
list](#community).

The Zulip project uses a system of labels in our [issue
tracker][gh-issues] to make it easy to find a project if you don't
have your own project idea in mind or want to get some experience with
working on Zulip before embarking on a larger project you have in
mind:

* [Integrations](https://github.com/zulip/zulip/labels/area%3A%20integrations).
  Integrate Zulip with another piece of software and contribute it
  back to the community!  Writing an integration can be a great first
  contribution.  There's detailed documentation on how to write
  integrations in [the Zulip integration writing
  guide](https://zulip.readthedocs.io/en/latest/integration-guide.html).

* [Bite Size](https://github.com/zulip/zulip/labels/bite%20size):
  Smaller projects that might be a great first contribution.

* [Documentation](https://github.com/zulip/zulip/labels/area%3A%20documentation):
  The Zulip project loves contributions of new documentation.

* [Help Wanted](https://github.com/zulip/zulip/labels/help%20wanted):
  A broader list of projects that nobody is currently working on.

* [Platform support](https://github.com/zulip/zulip/labels/Platform%20support):
  These are open issues about making it possible to install Zulip on a
  wider range of platforms.

* [Bugs](https://github.com/zulip/zulip/labels/bug): Open bugs.

* [Feature requests](https://github.com/zulip/zulip/labels/enhancement):
  Browsing this list can be a great way to find feature ideas to
  implement that other Zulip users are excited about.

* [2016 roadmap milestone](http://zulip.readthedocs.io/en/latest/roadmap.html):
  The projects that are
  [priorities for the Zulip project](https://zulip.readthedocs.io/en/latest/roadmap.html).
  These are great projects if you're looking to make an impact.

Another way to find issues in Zulip is to take advantage of our
`area:<foo>` convention in separating out issues.  We partition all of
our issues into areas like admin, compose, emoji, hotkeys, i18n,
onboarding, search, etc.  Look through our
[list of labels](https://github.com/zulip/zulip/labels), and click on
some of the `area:` labels to see all the tickets related to your
areas of interest.

If you're excited about helping with an open issue, make sure to claim
the issue by commenting the following in the comment section:
"**@zulipbot** claim". **@zulipbot** will assign you to the issue and
label the issue as **in progress**. For more details, check out
[**@zulipbot**](https://github.com/zulip/zulipbot).

You're encouraged to ask questions on how to best implement or debug
your changes -- the Zulip maintainers are excited to answer questions
to help you stay unblocked and working efficiently. It's great to ask
questions in comments on GitHub issues and pull requests, or
[on chat.zulip.org][czo-doc].  We'll direct longer discussions to
Zulip chat, but please post a summary of what you learned from the
chat, or link to the conversation, in a comment on the GitHub issue.

We also welcome suggestions of features that you feel would be
valuable or changes that you feel would make Zulip a better open
source project, and are happy to support you in adding new features or
other user experience improvements to Zulip.

If you have a new feature you'd like to add, we recommend you start by
opening a GitHub issue about the feature idea explaining the problem
that you're hoping to solve and that you're excited to work on it.  A
Zulip maintainer will usually reply within a day with feedback on the
idea, notes on any important issues or concerns, and and often tips on
how to implement or test it.  Please feel free to ping the thread if
you don't hear a response from the maintainers -- we try to be very
responsive so this usually means we missed your message.

For significant changes to the visual design, user experience, data
model, or architecture, we highly recommend posting a mockup,
screenshot, or description of what you have in mind to the
[#design](https://chat.zulip.org/#narrow/stream/design) stream on
[chat.zulip.org][czo-doc] to get broad feedback before you spend too
much time on implementation details.

Finally, before implementing a larger feature, we highly recommend
looking at the
[new feature tutorial](http://zulip.readthedocs.io/en/latest/new-feature-tutorial.html)
and [coding style guidelines](http://zulip.readthedocs.io/en/latest/code-style.html)
on ReadTheDocs.

Feedback on how to make this development process more efficient, fun,
and friendly to new contributors is very welcome!  Just send an email
to the [zulip-devel](#community) list with your thoughts.

When you feel like you have completed your work on an issue, post your
PR to the
[#code review](https://chat.zulip.org/#narrow/stream/code.20review)
stream on [chat.zulip.org][czo-doc].  This is our lightweight process
that gives other developers the opportunity to give you comments and
suggestions on your work.

## License

Copyright 2011-2017 Dropbox, Inc., Kandra Labs, Inc., and contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

The software includes some works released by third parties under other
free and open source licenses. Those works are redistributed under the
license terms under which the works were received. For more details,
see the ``docs/THIRDPARTY`` file included with this distribution.


[czo-doc]: https://zulip.readthedocs.io/en/latest/chat-zulip-org.html
