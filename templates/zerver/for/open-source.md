The Zulip core developers have decades of combined experience writing and
maintaining free and open source software. We use Zulip to keep contributors
engaged, efficiently make decisions, and fashion the day-to-day experience
of being a part of our project. No other chat product comes close to Zulip
in facilitating contributor engagement, making efficient use of maintainers'
time, and upholding the values of the FOSS community.

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
* The lack of organization in Slack message history (and its 10K
  message history limit) mean that users asking for help cannot
  effectively do self-service support.  This results in the community
  answering a lot of duplicate questions.

The overall effect is that Slack is a poor communication tool for
projects that want to have an inclusive, global, open source community
and effectively retain volunteer contributors.

------------------------------------------

Zulip's topic-based threading model solves these inclusiveness
problems:

* Contributors in any time zone can send messages and expect to get a
  reply and have an effective (potentially asynchronous) conversation
  with the rest of the community.
* Zulip's topic-based theading helps include part-time contributors in
  two major ways.  First, they can easily browse what conversations
  happened while they were away from the community for hours or days,
  and priorize which conversations to read now, skip, or leave unread
  to read on the weekend, allowing them to make the best use of their
  limited time.  Second, Zulip makes it easy for them to have public
  stream conversations with participation from maintainers and other
  contributors (potentially split over hours, days, or weeks as
  needed) about their contributions, allowing them to fully
  participate in the work of the community.
* Maintainers can effectively participate in a Zulip community without
  being continuously online.  Using Zulip's [keyboard
  shortcuts](/help/keyboard-shortcuts), it's extremely efficient to
  inspect every potentially relevant thread and reply wherever one's
  feedback is useful, and replying hours after a question was asked is
  still a good contributor experience.  As a result, maintainers can
  do multi-hour sessions of focus work while still being available to
  their community.

You can see this in action in our own
[chat.zulip.org](https://chat.zulip.org) community, which sends
thousands of messages a week.  We often get feedback from contributors
around the world that they love how responsive Zulip's project leader
is in public Zulip conversations.  We are able to achieve this despite
the project leader spending only 30 minutes a day managing the
community and spending most of his time integrating improvements into
Zulip.

Many communities that migrated from Slack, IRC, or Gitter to Zulip
tell us that Zulip helped them manage and grow an inclusive, healthy
open source community in a similar way.  We hope Zulip can help your
community succeed too!

------------------------------------------

Below, we've collected a list of [Zulip features](/features) that are
particularly useful to open source communities.

### Free hosting at zulipchat.com

No catch; the hosting is supported by (and is identical to) zulipchat.com's
commercial offerings. This offer extends to any community involved in
supporting free and open source software: development projects, foundations,
meetups, hackathons, conference committees, and more. If you’re not sure
whether your organization qualifies, send us an email at
support@zulipchat.com.

### Join without an invitation

Allow anyone to
[join without an invitation](/help/allow-anyone-to-join-without-an-invitation).
You can also link to your Zulip with a [badge](/help/linking-to-zulip)
in your readme document.

### Moderate your community

Moderation is a big part of making an open community work. Zulip was built
for open communities from the beginning and comes with
[moderation tools](/help/moderating-open-organizations) out of the box.

### Authenticate with GitHub

Allow (or require) users to
[authenticate with their GitHub account][github-auth], instead of with their
email address.
[github-auth]: https://github.com/zulip/zulip/blob/7e9926233/zproject/prod_settings_template.py#L112

### Import from Slack or Gitter

Import your existing organization from [Slack](/help/import-from-slack) or
[Gitter](/help/import-from-gitter).

### Syntax highlighting

[Full Markdown support](/help/format-your-message-using-markdown), including
syntax highlighting, makes it easy to discuss code, paste an error message,
or explain a complicated point. Full LaTeX support as well.

### Permalink from issues to chat

[Permalink to Zulip conversations](/help/link-to-a-message-or-conversation)
from your issue tracker. Zulip’s topic-based threading keeps conversations
coherent and organized.

### Link from chat to issues

Efficiently refer to issues or code reviews with notation like `#1234` or
`T1234`. You can set up any regex as a
[custom linkification filter](/help/add-a-custom-linkification-filter) for
your organization.

### Hundreds of integrations

Get events from GitHub, Travis CI, JIRA, and
[hundreds of other tools](/integrations) right in Zulip. Topics give each
issue its own place for discussion.

### Keep your IRC

Two-way integrations with IRC and Matrix, and one-way integration with
Slack (get Slack messages in Zulip).

### Quality data export

Our high quality [export](/help/export-your-organization) and
[import](https://zulip.readthedocs.io/en/latest/production/export-and-import.html)
tools ensure you can always move from
[zulipchat.com](https://zulipchat.com) hosting to your own servers.

### Scale to thousands of users

For those running Zulip at home, we’ve done a lot of work to ensure that
drive-by members of the community don’t consume too many disk or CPU
resources. A Zulip server with 1000 active members and 10000 inactive
members takes about as many resources as a Zulip server with 1000 active
members.

### Free and open source

Don’t like something? You can
[open an issue](https://github.com/zulip/zulip/issues),
[submit a patch](https://zulip.readthedocs.io/en/latest/development/overview.html),
[fork the project](https://github.com/zulip/zulip), or chat with us directly
at [chat.zulip.org](https://chat.zulip.org). All code, including the
[desktop](https://github.com/zulip/zulip-desktop) and
[mobile](https://github.com/zulip/zulip-mobile) apps, is under the Apache 2
license.

### Proven model

Check out [chat.zulip.org](https://chat.zulip.org) to see Zulip in action
for a project with ~5000 messages of developer discussion a week. The Zulip
project is the largest and fastest-growing open source group chat product,
both by number of contributors (300+) and by commit velocity (more than
Docker and Django combined).

### Public archive

Allow search engines to index your chat, with a read-only view of your
public streams. Zulip’s topic-based threading keeps conversations coherent
and organized, enabling a meaningful archive indexed by search engines.

Currently implemented as an [out-of-tree
tool](https://github.com/zulip/zulip_archive), though a native feature
built into the Zulip server is coming soon.

### Full-text search of all public history

Zulip's [full-text search](/help/search-for-messages) supports
searching the organization's entire public history via the
`streams:public` search operator, allowing Zulip to provide all the
benefits of a searchable project forum.

### Logged-out public access (coming soon)

Allow users to read public streams from your organization's Zulip
history without having to create an account.

