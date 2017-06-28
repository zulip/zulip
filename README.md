**[Zulip overview](#zulip-overview)** |
**[Community](#community)** |
**[Installing for production](#running-zulip-in-production)** |
**[Contributing](#contributing)** |
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

[![Build Status](https://travis-ci.org/zulip/zulip.svg?branch=master)](https://travis-ci.org/zulip/zulip) [![Coverage Status](https://img.shields.io/codecov/c/github/zulip/zulip.svg)](https://codecov.io/gh/zulip/zulip) [![docs](https://readthedocs.org/projects/zulip/badge/?version=latest)](http://zulip.readthedocs.io/en/latest/) [![Zulip chat](https://img.shields.io/badge/zulip-join_chat-brightgreen.svg)](https://chat.zulip.org) [![Twitter](https://img.shields.io/badge/twitter-@zuliposs-blue.svg?style=flat)](http://twitter.com/zuliposs)

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
  [twitter account](https://twitter.com/zuliposs).

* Last but not least, we use [GitHub](https://github.com/zulip/zulip)
to track Zulip-related issues (and store our code, of course).
Anybody with a GitHub account should be able to create Issues there
pertaining to bugs or enhancement requests.  We also use Pull Requests
as our primary mechanism to receive code contributions.

The Zulip community has a [Code of Conduct][code-of-conduct].

[zulip-devel]: https://groups.google.com/forum/#!forum/zulip-devel
[code-of-conduct]:https://zulip.readthedocs.io/en/latest/code-of-conduct.html

## Running Zulip in production

Zulip in production supports Ubuntu 14.04 Trusty and Ubuntu 16.04
Xenial. Work is ongoing on adding support for additional
platforms. The installation process is documented at
<https://zulip.org/server.html> and in more detail in [the
documentation](https://zulip.readthedocs.io/en/latest/prod-install.html).

## Contributing

Zulip welcomes all forms of contributions! Please read the [contributing
guidelines][contributing] for more information.

[contributing]: https://github.com/zulip/zulip/blob/master/CONTRIBUTING.md

## Google Summer of Code

We participated in
[GSoC](https://developers.google.com/open-source/gsoc/) in 2016 (with
[great results](https://blog.zulip.org/2016/10/13/static-types-in-python-oh-mypy/))
and [are participating](https://github.com/zulip/zulip.github.io/blob/master/gsoc-ideas.md)
in 2017 as well.

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
