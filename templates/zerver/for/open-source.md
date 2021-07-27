Below, we’ve collected a list of [Zulip features](/features) that are
particularly useful to open source communities. We also recommend
checking out [Zulip for communities](/for/communities) to learn how
Zulip empowers welcoming communities by making it easy to participate
on your own time.

<br />
<blockquote class="twitter-tweet"><p lang="en" dir="ltr">When we made the switch to <a href="https://twitter.com/zulip?ref_src=twsrc%5Etfw">@zulip</a> a few months ago for chat, never in my wildest dreams did I imagine it was going to become the beating heart of the community, and so quickly. It&#39;s a game changer. 🧑‍💻🗨️👩‍💻</p>&mdash; Dan Allen (@mojavelinux) <a href="https://twitter.com/mojavelinux/status/1409702273400201217?ref_src=twsrc%5Etfw">June 29, 2021</a></blockquote>
<br />

### Moderation suite.

Moderation is a big part of making an open community work. Zulip was built
for open communities from the beginning and comes with
[moderation tools](/help/moderating-open-organizations) out of the box.

### Open invitations.

Allow anyone to
[join without an invitation](/help/allow-anyone-to-join-without-an-invitation).
You can also link to your Zulip with a [badge](/help/linking-to-zulip)
in your readme document.

### Authenticate with GitHub or GitLab.

Allow (or require) users to authenticate with their [GitHub or GitLab
account](/help/configure-authentication-methods), instead of with a
username and password.
[github-auth]: https://github.com/zulip/zulip/blob/7e9926233/zproject/prod_settings_template.py#L112

### Import from Slack, Mattermost, Gitter, or Rocket.Chat.

Import your existing organization from [Slack](/help/import-from-slack),
[Mattermost](/help/import-from-mattermost),
[Gitter](/help/import-from-gitter), or
[Rocket.Chat](/help/import-from-rocketchat).

<br />
<blockquote class="twitter-tweet" data-cards="hidden"><p lang="en" dir="ltr">We just moved the Lichess team (~100 persons) to <a href="https://twitter.com/zulip?ref_src=twsrc%5Etfw">@zulip</a>, and I&#39;m loving it. The topics in particular make it vastly superior to slack &amp; discord, when it comes to dealing with many conversations.<br>Zulip is also open-source! <a href="https://t.co/lxHjf3YPMe">https://t.co/lxHjf3YPMe</a></p>&mdash; Thibault D (@ornicar) <a href="https://twitter.com/ornicar/status/1412672302601457664?ref_src=twsrc%5Etfw">July 7, 2021</a></blockquote>
<br />

### Collaborate on code and formulas

[Markdown code blocks](/help/code-blocks)
with syntax highlighting make it easy to discuss code, paste an error
message, or explain a complicated point. Native LaTeX support provides
the same benefits when talking about math.

You can also instantly copy a code block to your clipboard or transfer
it to an [external code playground](/help/code-blocks#code-playgrounds) to
interactively run and debug the code.

If your community primarily uses a single programming language,
consider setting a [default code block language](/help/code-blocks#default-code-block-language).

### Permalink to conversations.

Zulip makes it easy to get a [permanent link to a
conversation](/help/link-to-a-message-or-conversation), which you can
use in your issue tracker, forum, or anywhere else. Zulip’s
topic-based threading helps keep conversations coherent and organized
so they are useful for posterity.

### Link from chat to issues.

Efficiently refer to issues or code reviews with notation like `#1234` or
`T1234`. You can set up any regex as a
[custom linkification filter](/help/add-a-custom-linkifier) for
your organization.

### Hundreds of integrations.

Get events from GitHub, Travis CI, Jira, and
[hundreds of other tools](/integrations) right in Zulip. Topics give each
issue its own place for discussion.

>  “Wikimedia uses Zulip for its participation in open source
>  mentoring programs. Zulip’s threaded discussions help busy
>  organization administrators and mentors stay in close communication
>  with students during all phases of the programs.”

> — Srishti Sethi, Developer Advocate, Wikimedia Foundation

### Mirror IRC, Matrix, or Slack.

Two-way integrations with IRC, Matrix, and/or Slack using
[Matterbridge](https://github.com/42wim/matterbridge).

### Scales to 10,000s of members.

Zulip is designed to perform well in common use cases for open source
projects, with features like [soft
deactivation](https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html#soft-deactivation)
to make message delivery efficient even when sending to a stream with
10,000s of inactive subscribers.

### Full-text search of all public history.

Zulip’s [full-text search](/help/search-for-messages) supports
searching the organization’s entire public history via the
`streams:public` search operator, allowing Zulip to provide all the
benefits of a searchable project forum.

### Public archive.

Allow search engines to index your chat, with a read-only view of your
public streams. Zulip’s topic-based threading keeps conversations coherent
and organized, enabling a meaningful archive indexed by search engines.

Currently implemented as an [out-of-tree
tool](https://github.com/zulip/zulip-archive), though a native feature
built into the Zulip server is coming soon.

### Logged-out public access (coming soon).

[Coming soon](https://github.com/zulip/zulip/issues/13172): Allow
users to read and search public stream history in Zulip’s UI without
first creating an account.

### Quality data export.

Our high quality [export](/help/export-your-organization) and
[import](https://zulip.readthedocs.io/en/latest/production/export-and-import.html)
tools ensure you can always move from [Zulip Cloud](https://zulip.com)
hosting to your own servers.

### Free and open source.

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

So if there’s something we could improve to make Zulip the obvious
choice either for you or your community, [contact
us](/help/contact-support) and we'll do what we can to help!

>  “I highly recommend Zulip to other communities. We’re coming from
>  Freenode as our only real-time communication so the difference is
>  night and day. Slack is a no-go for many due to not being FLOSS,
>  and I’m concerned about vendor lock-in if they were to stop being
>  so generous. Slack’s threading model is much worse than Zulip’s
>  IMO. The streams/topics flow is an incredibly intuitive way to keep
>  track of everything that is going on.”

> — RJ Ryan, Mixxx Developer

<script async src="https://platform.twitter.com/widgets.js"></script>
