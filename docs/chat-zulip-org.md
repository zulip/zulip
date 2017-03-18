# The chat.zulip.org community

[chat.zulip.org](https://chat.zulip.org/) is the primary communication
forum for the Zulip community.

You can go through the simple signup process at that link, and then
you will soon be talking to core Zulip developers and other users.  To
get help in real time, you will have the best luck finding core
developers roughly between 16:00 UTC and 23:59 UTC, but the sun never
sleeps on the Zulip community.  Most questions get a reply
within minutes to a few hours, depending on the time of day.

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
* [#design](https://chat.zulip.org/#narrow/stream/design) is where we
  discuss the UI design and collect feedback on potential design
  changes.  We love feedback, so don't hesitate to speak up!
* [#documentation](https://chat.zulip.org/#narrow/stream/documentation)
  is where we discuss improving Zulip's user, sysadmin, and developer
  documentation.
* [#production help](https://chat.zulip.org/#narrow/stream/production.20help)
  is for production environment related discussions.
* [#test here](https://chat.zulip.org/#narrow/stream/test.20here) is
  for sending test messages without inconveniencing other users :).
  We recommend muting this stream when not using it.
* [#translation](https://chat.zulip.org/#narrow/stream/translation) is
  for discussing Zulip's translations.

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
