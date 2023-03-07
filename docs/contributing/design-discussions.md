# Design discussions

We discuss ideas for improving Zulip's user experience, interface, and visual
design in the [Zulip development
community](https://zulip.com/development-community/). The purpose of these
design discussions is to help us make smart, well-informed decisions about
design changes to the Zulip product. We want Zulip to work great for a diverse
array of users and organizations, and discussions in the development community
are an incredibly valuable source of insight and ideas. We welcome all
perspectives, respectfully shared.

Most design discussions take place in the [#design][design stream] stream in the
development community. Discussions about mobile app design happen in
[#mobile-team](https://chat.zulip.org/#narrow/stream/243-mobile-team), and
design of the terminal app is discussed in
[#zulip-terminal](https://chat.zulip.org/#narrow/stream/206-zulip-terminal).

## Guidelines for all participants

Everyone is encouraged to participate in design discussions! Your participation
greatly helps improve the product, especially when you focus your contributions
on supporting the productivity of the design team. The more we are able to
incorporate a variety of ideas, experiences, and perspectives into the
discussion, the better decisions we'll be able to make.

Please start by reviewing the guide to [how we
communicate](how-we-communicate.md) in the Zulip community. Also, when sharing
your ideas:

- Think about corner cases and interactions with existing features that the
  design will need to handle, and bring up problems with them, especially if they
  are not obvious. (E.g., “This component also appears with a darker background
  in the Drafts UI,” with a screenshot).

- Present technical considerations _where appropriate_. “X requires
  some refactoring that would take me another hour,” is probably not
  worth bringing up if X would produce a better user
  experience. “Adding X might require removing feature Y,” or “X is
  incompatible with Zulip's security model,” is important to present
  early.

Note that [#design][design stream] is a high-traffic stream, and thoughtful
participation takes time. Don’t let it prevent you from doing your own work. It
can be helpful to pick particular conversations to follow, where you feel that
you have insight to share.

## Participant roles

At this point, it will be helpful to define a few key roles in design
discussions:

- [Code contributor](#guidelines-for-code-contributors): Anyone working on a PR
  that includes some frontend changes.

- [Community moderator](#guidelines-for-community-moderators): Any core
  contributor or other experienced community member who is helping guide the
  discussion (with or without "moderator" permissions in the organization).

- **Design team**: Anyone working actively on the design of the feature at hand
  and/or overall design for the Zulip product.

- [Decision makers](#guidelines-for-decision-makers): Project maintainers
  responsible for design decisions, including design leaders, product leaders,
  and overall project leadership.

## Guidelines for code contributors

When you are working on a PR that includes frontend changes, you may find it helpful
to get interactive feedback on the design. The best way to do so is by posting a
message in the [#design][design stream] stream in the Zulip development
community.

### When to post

- The issue or a comment on your PR specifically asks you to get feedback in the
  [#design][design stream] stream.

- The issue you’re working on is not specific about some design point, and you
  would like advice.

- You’ve implemented an issue as described, but the UI doesn’t look good or
  seems awkward to use.

- You’re prototyping an idea that’s not fully fleshed out.

### Guidelines for requesting design feedback

You will get the most helpful feedback by sharing enough context for community
participants to understand what you're trying to do, and clearly stating the
questions you are looking for feedback on. Some advice:

- Start a new topic, or use an existing one if there is a topic linked from the
  issue you’re working on. If you’re starting a new topic, appending the issue
  or PR number (e.g., `#1234`) to the topic name will turn it into a handy link.

- Summarize the feature you’re working on. You should provide enough
  context for readers to understand your question, and include links
  to any relevant issues or in-progress PRs for additional background.

- Post screenshots, and screen captures if there is an interaction that
  screenshots fail to show.

  - You may want to post a few screenshots of different options you’re
    considering.

  - Screenshots should show enough of the app to evaluate how the new feature
    looks in its context, but not so much that it’s hard to see the feature.

  - Screen captures should demonstrate the feature with a minimal amount of
    extraneous content.

  - See [here](../tutorials/screenshot-and-gif-software.md) for some
    recommended tools.

- Post a clear question or set of questions that you need help with. What
  specifically are you looking for feedback on?

- Since you’ve been working on this issue, you have likely gained some expertise
  in this area. Educate others by sharing any tradeoffs and relevant
  considerations you’re aware of.

Keep in mind that the Zulip community is distributed around the world, and you
should not expect to get realtime feedback. However, feel free to bump the
thread if you don’t see a response after a couple of business days.

## Guidelines for community moderators

Any experienced community participant can guide design discussions, and help
make sure that we use everyone's time productively towards making the best
decisions we can.

### Improving the quality of discussions

Here are some suggestions for how you can help the community have a productive
design discussion:

- If a design discussion seems to have been derailed by a tangent or argument,
  consider moving the tangent to another topic so that the conversation can
  refocus on the questions at hand.

- If the direction of the discussion seems unproductive, you can explicitly
  suggest circling back to a topic where additional discussion seems valuable.

- If someone is repeating the same points in a way that’s unhelpful, you can let
  them know that you understand what they are saying and appreciate their
  feedback, but at this point would find it helpful to hear feedback from other
  participants. People may sometimes repeat themselves because they are not feeling
  heard.

- That said, sometimes the best way to deal with questions or feedback that
  don’t move the discussion forward is to let them go by without comment, rather
  than potentially getting into a protracted back-and-forth that derails the
  thread. Examples of such feedback include unmotivated personal opinions,
  proposals that ignore counterarguments that have already been discussed, etc.

- It’s totally fine to let the conversation slow down or die, especially if it
  seems to be going off-track. If the decision makers feel that they do not have
  enough feedback yet, they can revive the conversation as needed, and the pause
  can serve as a good reset.

If a conversation is going off-track and you are not sure how to fix it, please
ping someone on the core team to intervene and help get the conversion into a
better state.

### Moving threads to the most appropriate stream

Sometimes it helps to move (part of) a thread to a different stream, so that
it's seen by the appropriate audience.

- We generally aim to discuss raw user feedback on the product’s design in
  [#feedback](https://chat.zulip.org/#narrow/stream/137-feedback).
  The [#design][design stream] should be reserved for design aspects that we’re
  actively (considering) working on. This lets the design team focus on
  discussions that are expected to result in actionable decisions.

- If a discussion that started in another stream has shifted into the design
  phase, moving the discussion to [#design][design stream] helps the design team
  follow the conversation.

- Discussion of implementation-related decisions should ideally happen in
  [#frontend](https://chat.zulip.org/#narrow/stream/6-frontend). The line can
  sometimes blur (and that’s OK), but we should aim to move (parts of) the
  thread if there is an extensive conversation that belongs in the other stream.

- We use [#mobile-team](https://chat.zulip.org/#narrow/stream/243-mobile-team)
  for discussions of mobile app design, and
  [#zulip-terminal](https://chat.zulip.org/#narrow/stream/206-zulip-terminal) for
  terminal app design.

## Guidelines for decision makers

The main purpose of design discussions is to help us make the best design
decisions we can. Decision makers should guide the conversation to elicit the
ideas, feedback and advice they need from the community.

Ideally, design discussions should also help us learn as a community. Community
members who follow the conversation should get a better understanding of the
considerations behind the decisions being discussed, and thus be better able to
contribute to the next conversation.

### Managing the discussion

Decision makers should actively manage the discussion to make sure we're making
good use of everyone's time and attention, and getting useful feedback.

- Decision makers should aim to follow design threads closely and provide input
  early and often, so that conversations don’t get blocked waiting for their
  opinion.

- Decision makers should actively manage discussion threads when needed in order
  to seek the types of inputs that will help them. This may include outlining a
  set of alternatives to consider, posing questions to dig into someone’s
  feedback, asking for ideas to solve a specific design challenge, etc.

- Decision makers should explain the reasoning behind their proposed decisions,
  so that it’s possible to identify any gaps in their thinking, and in order to
  build a shared understanding in the community.

- That said, decision makers are not required to respond to every comment being
  made regarding a proposal, or to answer every question.

### From discussion to decision

There is a number of factors that affect when it’s time to move a thread from
discussion to a decision. In part, this depends on how significant a commitment
we are making with the decision at hand:

- We want to be very thoughtful about decisions that will take a lot of work to
  implement, and/or will be difficult to undo.

- We should try to come up with good designs for the features we're building,
  but sometimes it's difficult to foresee how an interaction will feel until we
  try it. Prototyping a UI we are not sure about is a normal part of the design
  process.

- When the decision results in filing a non-urgent issue, it’s fine to write up
  the conclusions on GitHub relatively quickly, and update the issue if more
  ideas come in later on.

- We should accept that sometimes an idea we decided on is just not working out,
  and be willing to go back to the drawing board or iterate further until we get
  to a state we're happy with.

With those considerations in mind, here are rough guidelines for when to move on
to a decision:

- For very small decisions, it may be enough to get a sanity-check from one or
  two well-informed community participants.

- For more significant decisions, one should generally allow at least 1-2 business
  days for discussion, to give core team members time to share their perspective
  if they have something to contribute.

- Beyond that minimum, the decision makers can move to the decision phase
  whenever they have enough input to make a well-informed decision. Here are
  some situations that would indicate that it’s time to move on:

  - There is general consensus on how to proceed. Or, there is consensus
    between the well-informed participants in the discussion.

  - For a relatively small decision, there is enough useful feedback to
    generate a solid proposal.

  - If the discussion is primarily rehashing old points, and doesn’t seem to
    be generating additional insights, it’s time to redirect the conversation
    or move on to a decision.

  - If the thread has died down, and the decision makers feel that they have
    enough information to go on. (If they don’t, the thread can be bumped.)

[design stream]: https://chat.zulip.org/#narrow/stream/101-design
