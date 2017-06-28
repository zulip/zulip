**[Installing for dev](#installing-the-zulip-development-environment)** |
**[Ways to contribute](#ways-to-contribute)** |
**[How to get involved](#how-to-get-involved-with-contributing-to-zulip)**

# Contributing

Zulip welcomes all forms of contributions! This page documents the
Zulip development process.

## Installing the Zulip Development environment

The Zulip development environment is the recommended option for folks
interested in trying out Zulip.  This is documented in [the developer
installation guide][dev-install].

## Ways to contribute

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
discussion mailing
list](https://github.com/zulip/zulip/blob/master/README.md#community) and uses
[GitHub issues ][gh-issues].  There are also lists for the
[Android][email-android] and [iOS][email-ios] apps.  Feel free to send any
questions or suggestions of areas where you'd love to see more documentation to
the relevant list!  Please report any security issues you discover to
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

## How to get involved with contributing to Zulip

First, subscribe to the Zulip [development discussion mailing
list](https://github.com/zulip/zulip/blob/master/README.md#community).

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
to the
[zulip-devel](https://github.com/zulip/zulip/blob/master/README.md#community)
list with your thoughts.

When you feel like you have completed your work on an issue, post your
PR to the
[#code review](https://chat.zulip.org/#narrow/stream/code.20review)
stream on [chat.zulip.org][czo-doc].  This is our lightweight process
that gives other developers the opportunity to give you comments and
suggestions on your work.

[czo-doc]: https://zulip.readthedocs.io/en/latest/chat-zulip-org.html
