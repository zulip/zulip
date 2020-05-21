Zulip is designed to facilitate the collaboration of thoughtful people
all around the world working on difficult problems, which perhaps
describes academic research better than any of our other use cases.

Zulip has long been popular with individual research groups, but
during the pandemic has started being used for large distributed
communities focused around research topics like Category Theory or the
Lean Theorem Prover.  We enthusiastically provide free hosting for
both use cases.

If you haven’t read [why Zulip](/why-zulip), read that first.  The
communication model challenges with the Slack/Discord/IRC model
discussed there are even more important for academic research:

* For most research problems, the experts who it's most useful to
  collaborate with are few in number and scattered across many places
  and time zones.  A Slack community is a bad experience if you’re
  rarely online at the same time as most other members; the result is
  often poor inclusivity of researchers whose ideas or knowledge could
  be critical to progress.

* One needs to be able to focus for several hours at a time in order
  to do effective research.  It's really important that one not feel
  like one's missing out or being constantly drawn back to check
  messages when doing focused research work.

  Because active participation in a busy Slack community fundamentally
  requires constant interruptions, one ends up making unpleasant
  choices between participating in the Slack community (and not doing
  focus work) or ignoring the Slack community (and not getting much
  benefit from it).

* Researchers, especially senior ones, often have interests in
  multiple areas.  Because catching up on history in an active Slack
  organization is a huge waste of time, this can make it hard to
  participate in a part-time fashion and provide one's expertise while
  personally focused on other projects.
* Writing to a busy Slack channel often means interrupting another
  existing conversation. This makes it harder for newer and shyer
  members to jump into the community. Often this disproportionately
  discourages talented individuals from groups already
  underrepresented in research.
* The lack of organization in Slack message history (and its 10K
  message history limit) mean that it's hard to find previous
  conversations that might have useful context.

The overall effect is that a busy Slack makes poor use of researchers'
time, and Slack is a poor choice for organizations that want to have
an inclusive, global community that many busy researchers happily
participate in.

------------------------------------------

Zulip’s topic-based threading model solves these problems:

* Participants in any time zone can send messages and expect to get a
  reply and have an effective (potentially asynchronous) conversation
  with the rest of the community.
* Zulip’s topic-based theading helps include part-time contributors in
  two major ways.  First, they can easily browse what conversations
  happened while they were away from the community, and prioritize
  which conversations to read now, skip, or read later (e.g. after
  that important talk or paper deadline).
* Researchers can effectively participate in a Zulip community without
  being continuously online.  Using Zulip’s [keyboard
  shortcuts](/help/keyboard-shortcuts), it’s extremely efficient to
  inspect every potentially relevant thread and reply wherever one’s
  feedback is useful, and replying hours after a question was asked is
  still a good contributor experience.  As a result, busy researchers
  can focus on teaching or multi-hour sessions of focused research,
  while still being able to catch up and participate fully in the
  community.
* Topics make it easier to provide a safe, welcoming, online
  community.  Asking a question never has to feel like an interruption
  of an ongoing conversation or like one's sticking one's neck out.

See our page [for open source projects](/for/open-source) for more
discussion of Zulip for open communities.

------------------------------------------

Below, we’ve collected a list of [Zulip features](/features) that are
particularly useful to academic research organizations (both formal
organizations and online communities focused around research topics
like Category Theory).

### Free hosting at zulipchat.com.

This free hosting is supported by (and is identical to)
zulipchat.com’s commercial offerings.  If you’re not sure whether your
organization qualifies, send us an email at support@zulipchat.com.

### Native LaTeX support powered by KaTeX

With Zulip, you can use inline LaTeX in the middle of a sentence or as
a display math block.  Zulip's LaTeX rendering is powered by
[KaTeX](https://katex.org); their [support
table](https://katex.org/docs/support_table.html) is a helpful
resource.

### Moderation suite.

Moderation is a big part of making an open community work. Zulip was built
for open communities from the beginning and comes with many
[moderation features](/help/moderating-open-organizations) out of the
box.

In addition, Zulip's threading makes it easy for a small group of busy
moderators to skim every thread and notice if there's anything that
needs their attention.

### Open invitations.

Allow anyone to [join without an
invitation](/help/allow-anyone-to-join-without-an-invitation).  You
can also link to your Zulip with a [badge](/help/linking-to-zulip) in
any associated source code repositories.

### Video call integration

With a single click, you create a [video call](/help/start-a-call),
making it convenient to do a quick call to hash out an idea.

### Import from Slack, Mattermost, or Gitter.

Import your existing organization from [Slack](/help/import-from-slack),
[Mattermost](/help/import-from-mattermost), or
[Gitter](/help/import-from-gitter).

### Syntax highlighting.

[Full Markdown support](/help/format-your-message-using-markdown), including
syntax highlighting, makes it easy to discuss code, paste an error message,
or explain a complicated point. Full LaTeX support as well.

If your community primarily uses a single programming language (or
only talks about math), consider setting a default language for syntax
highlighting.

### Permalink to conversations.

Zulip makes it easy to get a [permanent link to a
conversation](/help/link-to-a-message-or-conversation), which you can
record in emails, notes, talk slides, or anywhere else. Zulip’s
topic-based threading helps keep conversations coherent and organized
so they are useful for posterity.

### Hundreds of integrations.

Get events from GitHub, Travis CI, JIRA, and
[hundreds of other tools](/integrations) right in Zulip. Topics give each
issue its own place for discussion.

### Scales to 10,000s of members.

Zulip is designed to perform well in common use cases for public
discussio groups, with features like [soft
deactivation](https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html#soft-deactivation)
to make message delivery efficient even when sending to a stream with
10,000s of inactive subscribers.

### Full-text search of all public history.

Zulip’s [full-text search](/help/search-for-messages) supports
searching the organization’s entire public history via the
`streams:public` search operator, allowing Zulip to provide all the
benefits of a searchable forum or mailing list.

### Public archive.

Allow search engines to index your chat, with a read-only view of your
public streams. Zulip’s topic-based threading keeps conversations coherent
and organized, enabling a meaningful archive indexed by search engines.

Currently implemented as an [out-of-tree
tool](https://github.com/zulip/zulip-archive), though a native feature
built into the Zulip server is coming soon.  This archive tool allows
you to preserve your conversation history in a static HTML archive for
posterity.

### Logged-out public access (coming soon).

[Coming soon](https://github.com/zulip/zulip/issues/13172): Allow
users to read and search public stream history in Zulip’s UI without
first creating an account.

### Quality data export.

Our high quality [export](/help/export-your-organization) and
[import](https://zulip.readthedocs.io/en/latest/production/export-and-import.html)
tools ensure you can always move from
[zulipchat.com](https://zulipchat.com) hosting to your own servers.

### Free and open source.

Unlike many modern "open source" applications that are actually Open
Core, Zulip is 100% Free and Open Source software.  All code,
including for the [server](https://github.com/zulip/zulip),
[desktop](https://github.com/zulip/zulip-desktop),
[mobile](https://github.com/zulip/zulip-mobile), and beta
[terminal](https://github.com/zulip/zulip-terminal) apps is available
under the Apache 2 license.

### Created by former academics

Zulip's founder is a former MIT PhD student and we love helping
academic researchers succeed.  We prioritize feature requests from
academic research groups the same way we prioritize feature requests
from paying customers, so if there’s something we could improve to
make Zulip the obvious choice either for you or your research group,
[contact us](/help/contact-support) and we'll do what we can to help!
