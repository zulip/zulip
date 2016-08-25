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
at https://www.zulip.org.

[![Build Status](https://travis-ci.org/zulip/zulip.svg?branch=master)](https://travis-ci.org/zulip/zulip) [![Coverage Status](https://coveralls.io/repos/github/zulip/zulip/badge.svg?branch=master)](https://coveralls.io/github/zulip/zulip?branch=master)

## Community

There are several places online where folks discuss Zulip.

One of those places is our [public Zulip instance](https://zulip.tabbott.net/).
You can go through the simple signup process at that link, and then you
will soon be talking to core Zulip developers and other users.  To get
help in real time, you will have the best luck finding core developers
roughly between 16:00 UTC and 23:59 UTC.  Most questions get answered
within a day.

We have a [Google mailing list](https://groups.google.com/forum/#!forum/zulip-devel)
that is currently pretty low traffic.  It is where we do things like
announce public meetings or major releases.  You can also use it to
ask questions about features or possible bugs.

Last but not least, we use [GitHub](https://github.com/zulip/zulip) to
track Zulip-related issues (and store our code, of course).
Anybody with a Github account should be able to create Issues there
pertaining to bugs or enhancement requests.  We also use Pull
Requests as our primary mechanism to receive code contributions.

## Installing the Zulip Development environment

The Zulip development environment is the recommended option for folks
interested in trying out Zulip.  This is documented in [the developer
installation guide][dev-install].

## Running Zulip in production

Zulip in production only supports Ubuntu 14.04 right now, but work is
ongoing on adding support for additional platforms. The installation
process is documented at https://zulip.org/server.html and in more
detail in [the
documentation](https://zulip.readthedocs.io/en/latest/prod-install.html).

## Ways to contribute

Zulip welcomes all forms of contributions!  The page documents the
Zulip development process.

* **Pull requests**. Before a pull request can be merged, you need to
to sign the [Dropbox Contributor License Agreement][cla].  Also,
please skim our [commit message style guidelines][doc-commit-style].

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
discussion mailing list][gg-devel] and uses [GitHub issues
][gh-issues].  There are also lists for the [Android][email-android]
and [iOS][email-ios] apps.  Feel free to send any questions or
suggestions of areas where you'd love to see more documentation to the
relevant list!  Please report any security issues you discover to
zulip-security@googlegroups.com.

* **App codebases**. This repository is for the Zulip server and web
app (including most integrations); the [desktop][], [Android][], and
[iOS][] apps, are separate repositories, as are our [experimental
React Native iOS app][ios-exp] and [alpha Electron desktop
app][electron].

* **Glue code**. We maintain a [Hubot adapter][hubot-adapter] and several
integrations ([Phabricator][phab], [Jenkins][], [Puppet][], [Redmine][],
and [Trello][]), plus [node.js API bindings][node], and a [full-text search
PostgreSQL extension][tsearch], as separate repos.

* **Translations**.  Zulip is in the process of being translated into
10+ languages, and we love contributions to our translations.  See our
[translating documentation][transifex] if you're interested in
contributing!

[cla]: https://opensource.dropbox.com/cla/
[dev-install]: https://zulip.readthedocs.io/en/latest/dev-overview.html
[doc]: https://zulip.readthedocs.io/
[doc-commit-style]: http://zulip.readthedocs.io/en/latest/code-style.html#commit-messages
[doc-dirstruct]: http://zulip.readthedocs.io/en/latest/directory-structure.html
[doc-newfeat]: http://zulip.readthedocs.io/en/latest/new-feature-tutorial.html
[doc-test]: http://zulip.readthedocs.io/en/latest/testing.html
[electron]: https://github.com/zulip/zulip-electron
[gg-devel]: https://groups.google.com/forum/#!forum/zulip-devel
[gh-issues]: https://github.com/zulip/zulip/issues
[desktop]: https://github.com/zulip/zulip-desktop
[android]: https://github.com/zulip/zulip-android
[ios]: https://github.com/zulip/zulip-ios
[ios-exp]: https://github.com/zulip/zulip-mobile
[email-android]: https://groups.google.com/forum/#!forum/zulip-android
[email-ios]: https://groups.google.com/forum/#!forum/zulip-ios
[hubot-adapter]: https://github.com/zulip/hubot-zulip
[jenkins]: https://github.com/zulip/zulip-jenkins-plugin
[node]: https://github.com/zulip/zulip-node
[phab]: https://github.com/zulip/phabricator-to-zulip
[puppet]: https://github.com/matthewbarr/puppet-zulip
[redmine]: https://github.com/zulip/zulip-redmine-plugin
[trello]: https://github.com/zulip/trello-to-zulip
[tsearch]: https://github.com/zulip/tsearch_extras
[transifex]: https://zulip.readthedocs.io/en/latest/translating.html#testing-translations
[z-org]: https://github.com/zulip/zulip.github.io

## How to get involved with contributing to Zulip

First, subscribe to the Zulip [development discussion mailing
list][gg-devel].

The Zulip project uses a system of labels in our [issue
tracker][gh-issues] to make it easy to find a project if you don't
have your own project idea in mind or want to get some experience with
working on Zulip before embarking on a larger project you have in
mind:

* [Integrations](https://github.com/zulip/zulip/labels/integrations).
  Integrate Zulip with another piece of software and contribute it
  back to the community!  Writing an integration can be a great first
  contribution.  There's detailed documentation on how to write
  integrations in [the Zulip integration writing
  guide](https://zulip.readthedocs.io/en/latest/integration-guide.html).

* [Bite Size](https://github.com/zulip/zulip/labels/bite%20size):
  Smaller projects that might be a great first contribution.

* [Documentation](https://github.com/zulip/zulip/labels/documentation):
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

* [2016 roadmap milestone](http://zulip.readthedocs.io/en/latest/roadmap.html): The
  projects that are [priorities for the Zulip project](https://zulip.readthedocs.io/en/latest/roadmap.html).  These are great projects if you're looking to make an impact.

If you're excited about helping with an open issue, just post on the
conversation thread that you're working on it.  You're encouraged to
ask questions on how to best implement or debug your changes -- the
Zulip maintainers are excited to answer questions to help you stay
unblocked and working efficiently.

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
screenshot, or description of what you have in mind to zulip-devel@ to
get broad feedback before you spend too much time on implementation
details.

Finally, before implementing a larger feature, we highly recommend
looking at the new feature tutorial and coding style guidelines on
ReadTheDocs.

Feedback on how to make this development process more efficient, fun,
and friendly to new contributors is very welcome!  Just send an email
to the Zulip Developers list with your thoughts.

## License

Copyright 2011-2015 Dropbox, Inc.

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
see the ``THIRDPARTY`` file included with this distribution.
