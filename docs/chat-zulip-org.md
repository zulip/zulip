# The chat.zulip.org community

[chat.zulip.org](https://chat.zulip.org/) is the primary communication
forum for the Zulip community.  It is a Zulip server that you can
connect to from any modern web browser.

You can go through the simple signup process at that link, and then
you will soon be talking to core Zulip developers and other users.  To
get help in real time, you will have the best luck finding core
developers roughly between 17:00 UTC and 2:00 UTC or during [office
hours and sprints](#office-hours-and-sprints), but the sun never
sleeps on the Zulip community.  Most questions get a reply within
minutes to a few hours, depending on the time of day.

## This is a bleeding edge development server

The chat.zulip.org server is frequently deployed off of `master` from
the Zulip Git repository, so please point out anything you notice that
seems wrong!  We catch many bugs that escape code review this way.

The chat.zulip.org server is a development and testing server, not a
production service, so don't use it for anything mission-critical,
secret/embarrassing, etc.

## Community conventions

* Send any test messages to
  [#test here](https://chat.zulip.org/#narrow/stream/test.20here) or
  as a PM to yourself to avoid disrupting others.
* When asking for help, provide the details needed for others to help
  you.  E.g. include the full traceback in a code block (not a
  screenshot), a link to the code or a WIP PR you're having trouble
  debugging, etc.
* Ask questions on streams rather than PMing core contributors.
  You'll get answers faster since other people can help, and it makes
  it possible for other developers to learn from reading the discussion.
* Use @-mentions sparingly.  Unlike IRC or Slack, in Zulip, it's
  usually easy to see which message you're replying to, so you don't
  need to mention your conversation partner in every reply.
  Mentioning other users is great for timely questions or making sure
  someone who is not online sees your message.
* Converse informally; there's no need to use titles like "Sir" or "Madam".
* Use gender-neutral language.
* Follow the [community code of conduct](code-of-conduct.html).
* Participate!  Zulip is a friendly and welcoming community, and we
  love meeting new people, hearing about what brought them to Zulip,
  and getting their feedback.  If you're not sure where to start,
  introduce yourself and your interests in
  [#new members](https://chat.zulip.org/#narrow/stream/new.20members),
  using your name as the topic.

## Streams

There are a few streams worth highlighting that are relevant for
everyone, even non-developers:

* [#announce](https://chat.zulip.org/#narrow/stream/announce) is for
  announcements and discussions thereof; we try to keep traffic there
  to a minimum.
* [#feedback](https://chat.zulip.org/#narrow/stream/feedback) is for
  posting feedback on Zulip.
* [#design](https://chat.zulip.org/#narrow/stream/design) is where we
  discuss the UI design and collect feedback on potential design
  changes.  We love feedback, so don't hesitate to speak up!
* [#user community](https://chat.zulip.org/#narrow/stream/user.20community) is
  for Zulip users to discuss their experiences using and adopting Zulip.
* [#production help](https://chat.zulip.org/#narrow/stream/production.20help)
  is for production environment related discussions.
* [#test here](https://chat.zulip.org/#narrow/stream/test.20here) is
  for sending test messages without inconveniencing other users :).
  We recommend muting this stream when not using it.

There are dozens of streams for development discussions in the Zulip
community (e.g. one for each app, etc.); check out the
[Streams page](https://chat.zulip.org/#streams/all) to see the
descriptions for all of them.  Relevant to almost everyone are these:

* [#checkins](https://chat.zulip.org/#narrow/stream/checkins) is for
  progress updates on what you're working on and its status; usually
  folks post with their name as the topic.  Everyone is welcome to
  participate!
* [#development help](https://chat.zulip.org/#narrow/stream/development.20help)
  is for asking for help with any Zulip server/webapp development work
  (use the app streams for help working on one of the apps).
* [#code review](https://chat.zulip.org/#narrow/stream/code.20review)
  is for getting feedback on your work.  We encourage all developers
  to comment on work posted here, even if you're new to the Zulip
  project; reviewing other PRs is a great way to develop experience,
  and even just manually testing a proposed new feature and posting
  feedback is super helpful.
* [#documentation](https://chat.zulip.org/#narrow/stream/documentation)
  is where we discuss improving Zulip's user, sysadmin, and developer
  documentation.
* [#translation](https://chat.zulip.org/#narrow/stream/translation) is
  for discussing Zulip's translations.
* [#learning](https://chat.zulip.org/#narrow/stream/learning) is for
  posting great learning resources one comes across.

## Chat meetings

We have regular chat meetings on Zulip to coordinate work on various
parts of the Zulip project.  While most developer discussions happen
asynchonrously, these meetings are used mainly to coordinate work
within a major area of Zulip.  These meetings are usually scheduled in
Pacific time mornings, since that seems to be the best time for our
global contributor base (the part of the world where it's the deep
middle of the night is the Pacific Ocean).

Anyone is welcome to attend and contribute to the discussions in these
meetings, and they're a great time to stop by and introduce yourself
if you'd like to get involved (though really, any time is, so).

Here are the regular meetings that exist today along with their usual
times (actual times are listed in the linked agenda documents):

* Mobile team on
[#mobile](https://chat.zulip.org/#narrow/stream/mobile), generally
Wednesdays at 10AM Pacific time.  [Agendas][mobile-agendas].

* Backend/infrastructure team on
[#backend](https://chat.zulip.org/#narrow/stream/backend), generally
Fridays at 10AM Pacific time.  [Agendas][infra-agendas].

* Bots and integrations team on
[#integrations](https://chat.zulip.org/#narrow/stream/integrations),
generally Fridays at 9AM Pacific time.  [Agendas][bots-agendas].

[mobile-agendas]: https://paper.dropbox.com/doc/Zulip-mobile-agendas-nVdb9I7SDiom9hY8Zw8Ge
[infra-agendas]: https://paper.dropbox.com/doc/Zulip-infrastructure-team-agendas-kGyCvF2u2kLcZ1Hzyd9iD
[bots-agendas]: https://paper.dropbox.com/doc/Zulip-bots-and-integrations-agendas-3MR8NAL3fg4tIEpfb5jyx

### Office hours and sprints

We also do project-wide ad-hoc "office hours" and remote sprints
irregularly, about once a month.

Anyone can schedule one: announce it in
[#announce](https://chat.zulip.org/#narrow/stream/announce) and on
[the zulip-devel mailing list](https://groups.google.com/forum/#!forum/zulip-devel)
a few days ahead of time, and ideally, tell
[Sumana](https://chat.zulip.org/#narrow/sender/18-sh) so she can put
it on [the public Zulip meetings calendar][meetings-calendar].

*Office hours* are simply times for us to informally discuss current
global project priorities, find out what questions people have, and so
on. We set them up so people know there'll be more people around at a
particular time to chat. You don't need to RSVP and you don't need to
show up on time or stop conversations when the "hour" stops. They
start in [#general](https://chat.zulip.org/#narrow/stream/general) and
conversations move into other streams and topics as they come up.

*Sprints* are times when Zulip developers get together in chat, and
sometimes in person, to work on related issues at the same time.

[meetings-calendar]: https://calendar.google.com/calendar/embed?src=ktiduof4eoh47lmgcl2qunnc0o@group.calendar.google.com
