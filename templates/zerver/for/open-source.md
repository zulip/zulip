The Zulip core developers have decades of combined experience leading
and growing open source communities. We use Zulip to fashion the
day-to-day experience of being a part of our project. No other chat
product comes close to Zulip in facilitating contributor engagement,
facilitating inclusion, and making efficient use of everyone's time.

If you haven't read [why Zulip](/why-zulip), read that first.  The
challenges with the Slack/Discord/IRC model discussed there are even
more important for open source projects:

* Open source contributors are scattered all over the world and in
  every time zone.  Traditional open source communication tools like
  email, forums, and issue trackers work well in this context, because
  you can communicate effectively asynchronously.  A Slack community
  is a bad experience if you're rarely online at the same time as most
  other members, and a result, Slack represents a huge regression in
  the global inclusivity of open source projects.
* Most contributors and potential contributors have other fulltime
  obligations and can only spend a few hours a week on an open source
  project.  Because catching up on history in an active Slack
  organization is a huge waste of time, these part-time community
  members cannot efficiently use their time participating in an active
  Slack.  So either they don't participate in the Slack, or they do,
  and their other contributions to the project suffer.
* Maintainers are busy people and almost uniformly report that they
  wish they had more time to do focus work on their project.  Because
  active participation in Slack fundamentally requires constant
  interruptions, maintainers end up making unpleasant choices between
  participating in the Slack community (limiting their ability to do
  focus work) or ignoring the Slack community (leaving it effectively
  without their input and potentially unmoderated).
* Writing to a busy Slack channel often means interrupting another existing
  conversation. This makes it harder for newer and shyer members to jump into
  the community. Often this disproportionately affects groups already
  underrepresented in open source communities.
* The lack of organization in Slack message history (and its 10K
  message history limit) mean that users asking for help cannot
  effectively do self-service support.  This results in the community
  answering a lot of duplicate questions.

The overall effect is that Slack is a poor communication tool for
projects that want to have an inclusive, global, open source community
and effectively retain volunteer contributors.

------------------------------------------

Zulip's topic-based threading model solves these problems:

* Contributors in any time zone can send messages and expect to get a
  reply and have an effective (potentially asynchronous) conversation
  with the rest of the community.
* Zulip's topic-based theading helps include part-time contributors in
  two major ways.  First, they can easily browse what conversations
  happened while they were away from the community, and prioritize
  which conversations to read now, skip, or read later (e.g. on the
  weekend).  Second, Zulip makes it easy for them to have public
  conversations with participation from maintainers and other
  contributors (potentially split over hours, days, or weeks as
  needed), allowing them to fully participate in the work of the
  community.
* Maintainers can effectively participate in a Zulip community without
  being continuously online.  Using Zulip's [keyboard
  shortcuts](/help/keyboard-shortcuts), it's extremely efficient to
  inspect every potentially relevant thread and reply wherever one's
  feedback is useful, and replying hours after a question was asked is
  still a good contributor experience.  As a result, maintainers can
  do multi-hour sessions of focus work while still being available to
  their community.
* Every contributor has their own space to start a conversation (we
  recommend new contributors start a topic with their name as the
  topic). Asking a question never has to be an interruption of another
  conversation.

You can see this in action in our own
[chat.zulip.org](https://chat.zulip.org) community, which sends
thousands of messages a week.  We often get feedback from contributors
around the world that they love how responsive Zulip's project leaders
are in public Zulip conversations.  We are able to achieve this
despite the project leaders collectively spending only a few hours a
day managing the community and spending most of their time integrating
improvements into Zulip.

Many communities that migrated from Slack, IRC, or Gitter to Zulip
tell us that Zulip helped them manage and grow an inclusive, healthy
open source community in a similar way.  We hope Zulip can help your
community succeed too!

------------------------------------------

Below, we've collected a list of [Zulip features](/features) that are
particularly useful to open source communities.

### Free hosting at zulipchat.com

The hosting is supported by (and is identical to) zulipchat.com's
commercial offerings. This offer extends to any community involved in
supporting free and open source software: development projects, foundations,
meetups, hackathons, conference committees, and more. If you’re not sure
whether your organization qualifies, send us an email at
support@zulipchat.com.

### Moderation suite

Moderation is a big part of making an open community work. Zulip was built
for open communities from the beginning and comes with
[moderation tools](/help/moderating-open-organizations) out of the box.

### Open invitations

Allow anyone to
[join without an invitation](/help/allow-anyone-to-join-without-an-invitation).
You can also link to your Zulip with a [badge](/help/linking-to-zulip)
in your readme document.

### Authenticate with GitHub

Allow (or require) users to
[authenticate with their GitHub account][github-auth], instead of with their
email address.
[github-auth]: https://github.com/zulip/zulip/blob/7e9926233/zproject/prod_settings_template.py#L112

### Import from Slack, Mattermost, or Gitter

Import your existing organization from [Slack](/help/import-from-slack),
[Mattermost](/help/import-from-mattermost), or
[Gitter](/help/import-from-gitter).

### Syntax highlighting

[Full Markdown support](/help/format-your-message-using-markdown), including
syntax highlighting, makes it easy to discuss code, paste an error message,
or explain a complicated point. Full LaTeX support as well.

### Permalink to conversations

Zulip makes it easy to get a [permanent link to a
conversation](/help/link-to-a-message-or-conversation), which you can
use in your issue tracker, forum, or anywhere else. Zulip’s
topic-based threading helps keep conversations coherent and organized
so they are useful for posterity.

### Link from chat to issues

Efficiently refer to issues or code reviews with notation like `#1234` or
`T1234`. You can set up any regex as a
[custom linkification filter](/help/add-a-custom-linkification-filter) for
your organization.

### Hundreds of integrations

Get events from GitHub, Travis CI, JIRA, and
[hundreds of other tools](/integrations) right in Zulip. Topics give each
issue its own place for discussion.

### Mirror IRC or Matrix

Two-way integrations with [IRC](/integrations/doc/irc) and
[Matrix](/integrations/doc/matrix), and one-way integration with
[Slack](/integrations/doc/slack) (get Slack messages in Zulip).

### Scales to 10,000s of members

Zulip is designed to perform well in common use cases for open source
projects, with features like [soft
deactivation](https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html#soft-deactivation)
to make message delivery efficient even when sending to a stream with
10,000s of inactive subscribers.

### Full-text search of all public history

Zulip's [full-text search](/help/search-for-messages) supports
searching the organization's entire public history via the
`streams:public` search operator, allowing Zulip to provide all the
benefits of a searchable project forum.

### Public archive

Allow search engines to index your chat, with a read-only view of your
public streams. Zulip’s topic-based threading keeps conversations coherent
and organized, enabling a meaningful archive indexed by search engines.

Currently implemented as an [out-of-tree
tool](https://github.com/zulip/zulip_archive), though a native feature
built into the Zulip server is coming soon.

### Logged-out public access (coming soon)

[Coming soon](https://github.com/zulip/zulip/issues/13172): Allow
users to read and search public stream history in Zulip's UI without
first creating an account.

### Quality data export

Our high quality [export](/help/export-your-organization) and
[import](https://zulip.readthedocs.io/en/latest/production/export-and-import.html)
tools ensure you can always move from
[zulipchat.com](https://zulipchat.com) hosting to your own servers.

### Free and open source

Unlike many modern "open source" applications that are actually Open
Core, Zulip is 100% Free and Open Source software.  All code,
including for the [server](https://github.com/zulip/zulip),
[desktop](https://github.com/zulip/zulip-desktop),
[mobile](https://github.com/zulip/zulip-mobile), and beta
[terminal](https://github.com/zulip/zulip-terminal) apps is available
under the Apache 2 license.

We love helping other open source communities and prioritize feature
requests from open source communities the same way we prioritize
feature requests from paying customers.

So if there's something we could improve to make Zulip the obvious
choice either for you or your community, [open an
issue](https://github.com/zulip/zulip/issues), [submit a
patch](https://zulip.readthedocs.io/en/latest/development/overview.html),
[email us](mailto:support@zulipchat.com), or chat with us directly at
[chat.zulip.org](https://chat.zulip.org).
