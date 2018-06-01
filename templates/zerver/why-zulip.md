# Why Zulip?

There are a lot of team chat apps. So why did we build Zulip?

We talk about Slack in the discussion below, but the problems apply equally
to other apps with Slack's conversation model, including Hipchat, IRC,
Mattermost, Discord, Spark, and others.

## Slack channels are a huge waste of your time

Anyone who wakes up to this frequently can tell you it is not fun.

![slack unreads](/static/images/why-zulip/slack-unreads.png)

The lack of organization and context in Slack channels means that anyone
using Slack heavily has to manually scan through hundreds of messages a day
to find the content that is relevant to them.

## Senior people rarely use Slack channels

Slack channels are even worse for managers and other people involved in
multiple projects. Even modest usage of Slack leads to more channel messages
a day than most managers have time to handle.

In practice, in organizations that use Slack, many senior personnel
(sensibly) don't read their channel messages at all, or only read a handful
of smaller channels. This means you now have a company communication
platform ... with everyone but the decision makers.

## Channels rapidly devolve into GIF posts

Once a channel reaches dozens of messages a day, substantive conversations
become increasingly difficult or even impossible. If you send a thoughtful
question at 10am, anyone who checks in after lunch is too late to reply,
since someone else will have already started another conversation in that
channel. This means that even moderately busy channels can't be used for
serious discussion, and they devolve into a mix of quick questions and
random spam.

## Remote workers can't participate

If channel conversations only last an hour or two, workers in different
timezones can only communicate over channels during the narrow window when
everyone is online.

As a pointed illustration of how hard remote work is on Slack: The company
that makes Slack advertises no remote job positions (positions where you
could work from anywhere). By contrast, the Zulip team is distributed across
a dozen time zones, and uses only Zulip and GitHub issues for communication
(no email lists, video meetings, etc).

## Teams that love Slack are often mostly using DMs and small channels

Slack is great for private messages ("DMs"), integrations, and quick
questions. Most glowing reviews of Slack are actually of these aspects of
Slack.  We find that even people that love Slack typically send the vast
majority of their messages in DMs or to small channels.

## So where is the communication happening?

In organizations that have adopted Slack, mostly the same place it happened
before they adopted Slack: email, meetings, and small group chat.

Email is great for asynchronous work; that’s a big part of why everyone uses
it. Email’s simple subject line model, used properly, can solve all of the
issues above.  However, it is too slow and clunky for serious discussion;
even a 50 message thread starts to feel unwieldy. And it lacks many of the
conversational features of modern chat apps, like instant delivery of
messages, typing notifications, emoji reactions, at-mentions, and more.

Meetings are the current state-of-the-art for larger conversations where
managers, PMs, or other senior people are present. However, meetings are
often extremely inefficient. Participants may need to be present for an
hour-long meeting when their input is only needed for five minutes portion
of the discussion. If someone is unable to attend the meeting, their input
is lost. Someone has to take notes for there to be any record of what
happened or any record of follow-ups. And meetings add delay and scheduling
overhead to decisions.

Finally, small group chat works for the short term, but it doesn't build
knowledge within the team, and leads to only managers having the full
picture on projects. Having discussions accessible to larger lists allows
more stakeholders to stay in the loop.

## Asynchronous communication is fundamental to productive work

These problems are all symptoms of the underlying fact that the channel
model used by Slack and similar tools is a really bad way to structure
asynchronous communication.

However, asynchronous communication is fundamental to how work happens today.

* Managers, PMs, and others in meetings all day need to reply to things in
  batch, either in the few minutes they have between meetings, or at the end
  of the day.
* Anyone in a different timezone or on a different work schedule than the
  rest of the team has parts of their day where they are working
  asynchronously.
* Individual contributors cannot do focused work if they need to check their
  communication tool every 5 minutes to use it.  Asynchronous communication
  is essential to being able to focus for an hour or more, which has been
  shown to have a huge impact on developer productivity and happiness.

The fact that you can't do asynchronous work in Slack channels puts a
ceiling on how useful Slack can be to an organization.

## Ok. What does Zulip do differently?

> Zulip’s unique threading saves me well over an hour a day in working with
> our distributed team of engineers and PMs across 7+ time zones. We tried
> Slack, Mattermost, and other team chat products that claim to support
> threading, and nothing handles synchronous and asynchronous communication
> so intuitively.
>
> -Jacinda Shelly, CTO, Doctor On Demand

Zulip provides the benefits of real-time chat, while solving the problems
discussed above.  Our solution is inspired by email’s highly effective
threading model.  In Zulip, every channel message has a topic, just like
every message in email has a subject line. (Channels are called streams in
Zulip.)

![zulip topics](/static/images/why-zulip/zulip-topics.png)

Topics hold Zulip conversations together, just like subject lines hold email
conversations together.  They allow you to efficiently catch up on messages
and reply in context, even to conversations that started hours or days ago.

![zulip reply later](/static/images/why-zulip/zulip-reply-later.png)

It's simple in concept, but transforms what you can do in chat. Managers can
batch-reply to messages at the end of the day. Discussions can be moved from
meetings and email to chat. Individual contributors can do focused work
instead of paging through GIFs making sure they don't miss anything
important.

> "Zulip's topic-based threading helps us manage discussions with clarity,
> ensuring the right people can pay attention to the right messages. This
> makes our large-group discussion far more manageable than what we've
> experienced with Skype and Slack."
>
> -Grahame Grieve, founder, FHIR health care standards body

## Further reading

- [Zulip features](../features)
- [Plans and pricing](../plans)
- [Zulip for companies](../for/companies)
- [Zulip for open source organizations](/for/open-source)
- [Zulip for working groups and communities](/for/working-groups-and-communities)
