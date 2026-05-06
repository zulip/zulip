# Designing changes to the Zulip API

One of Zulip's strengths is its clean, [well-documented][api-docs-doc]
API which clients use to talk to the server.
[This HTTP-based API][api-docs] is used equally by the Zulip web/desktop app,
the official mobile app and terminal app, and
numerous third-party integrations, bots, and tools
written by many different Zulip users.

Many new Zulip features involve making changes to the API.
Because the Zulip API is so widely used, it's important that we
do a good job of those changes, in several respects:

- All API changes must be _compatible_, meaning they
  don't cause existing Zulip clients
  (e.g., existing installs of the Zulip mobile app)
  to break.

- All API changes should be _clean APIs_, meaning
  the new API features have crisp meanings,
  will support clients implementing the feature in a natural way,
  and have clear names that point accurately to the meanings.

- All API changes should be _clearly documented_
  and follow our [API documentation conventions][api-docs-doc].

The last point is covered in [its own document][api-docs-doc].
This document describes how we accomplish the other two:
compatible API changes, and clean APIs.

[api-docs-doc]: ../documentation/api.md
[api-docs]: https://zulip.com/api/
[#api design]: https://chat.zulip.org/#narrow/channel/378-api-design

## API change process, in short

There are two essential rules for how we make API changes:

1. When considering an API change,
   **always discuss it in the [#api design][] channel**.

2. Before merging a PR with an API change,
   always make sure the change has been approved in that channel.

As long as you follow those two rules,
the maintainers who manage that channel
can guide you through all the other aspects of the process,
as described in this document.

(For what counts as an "API change", see the next section.)

## What is an API change?

An "API change" is anything that
adds, removes, or changes the meaning of
anything that the server sends to clients,
or that the server accepts from clients.

For example, this includes:

- adding or removing an endpoint (editing `zproject/urls.py`)
- adding or removing parameters of an endpoint
- adding or removing any fields in the initial snapshot
  (the [/api/register-queue][] response)
  or any other endpoint's response
- changing the type of any of the above,
  including adding new values to an enum type
- renaming or moving any of the above
- changing the meaning of any existing parameter or field

In general, almost any change that touches
the API spec file `zerver/openapi/zulip.yaml`
will be an API change.
(The few exceptions are things like clarifying the wording
of existing documentation there.)
Conversely, for most — but not all! — API changes,
if you write tests that exercise the changes,
then our test suite will ensure there's a corresponding change
in the API spec file.

Some types of API changes that one might not realize are API changes:

- Any change to the structure of "[Zulip content HTML][]",
  the HTML that the server emits for message content
  (and a few other places like channel descriptions).
  This includes:

  - new CSS classes
  - new `data-*` attributes or other attributes
  - existing CSS classes or attributes appearing in new places,
    or disappearing from some existing places

- Any change to [push notification payloads][].

All types of API changes need to
follow the principles in this document
and be discussed in [#api design][].

[/api/register-queue]: https://zulip.com/api/register-queue
[Zulip content HTML]: https://zulip.com/api/message-formatting
[push notification payloads]: https://zulip.com/api/mobile-notifications

## API design approval

The [#api design][] channel has a few maintainers who have taken on
the specific responsibility of managing that channel's discussions.
Typically these include the lead of the Zulip mobile team,
and one or two Zulip maintainers who work primarily in
the server and/or web app.

A given API change proposal is approved when
one of the channel's maintainers says,
in the change's thread in the channel,
that the change is approved.

Typically this will happen only after reaching consensus
between both a mobile maintainer and a server or web maintainer,
each agreeing that the change looks good from their perspective.

If one of the channel maintainers has said the change looks good
and you're not sure if they mean only from their perspective
(so are waiting for a perspective from
a maintainer of the other system)
or they mean the change is approved and ready to merge,
please ask so they can make the status more explicit.

## API compatibility

All changes to the Zulip API must be compatible:
they must not cause existing Zulip clients to break.

For some kinds of API changes this is easy.
For others it takes more work.

### Changes that are automatically compatible

Some API changes are automatically compatible
with no further effort.

A first question for any API change is to determine
whether this happy circumstance applies,
because it saves us from needing to do the
API compatibility work described in the next section.

Some of the principles that maintainers will use
in determining if a change is automatically compatible are:

- Adding new endpoints, or new parameters on an endpoint,
  is always compatible because existing clients
  won't interact with these.

  - This is true only so long as the meaning of existing requests
    doesn't change, though.
    For example, if a new parameter has a default
    which is different from the endpoint's old behavior,
    then that's a change in the meaning of the endpoint
    when the new parameter isn't sent,
    and therefore may not be compatible.

- Adding new fields to an endpoint's response,
  or a JSON object nested inside a response,
  is always compatible.
  A correct Zulip client already ignores any field it doesn't expect.

  - Conversely, this means that if an existing piece of API
    starts including by default data objects it previously didn't,
    that change is _not_ automatically compatible,
    even if the new objects have some new field to distinguish them —
    because existing clients will ignore that field.

    For example, when we started including archived channels in the
    lists of channels in [/api/register-queue][], we didn't just start
    including them while adding an `"is_archived": true` flag to them,
    because if we did that then existing clients would have innocently
    treated those as additional non-archived channels (and therefore
    wrongly shown them in the list-of-channels screen, etc.).
    Instead more compatibility work was required, per the next section.

- In [Zulip content HTML][],
  adding new attributes is compatible.
  Adding new CSS classes, however, is _not_ automatically compatible.
  In general, most changes to Zulip content HTML
  are not automatically compatible.

  Relevant discussion: [#api design > HTML pattern for truly inline images @ 💬](https://chat.zulip.org/#narrow/channel/378-api-design/topic/HTML.20pattern.20for.20truly.20inline.20images/near/2348105)

- If a change affects only API features that are used only by the
  Zulip web app and no other clients, then the change is compatible
  even if it does things like remove or rename a field.

  Typically this is true if a feature is used only in the settings UI.
  It's sometimes true of other features too.

  These changes are compatible because the web app is deployed with
  the server, and clients automatically reload into the new web app
  version soon after a server upgrade. Managing such changes typically
  require at most require the Zulip Cloud team to split the web and
  server changes across two consecutive deployments, which does not
  justify permanent compatibility code.

  To determine if this is the case:

  - Check that the mobile app doesn't use the affected feature.
    Always confirm this explicitly before deciding the feature
    isn't used; occasionally the app does depend on an API feature
    one wouldn't have expected.

    This check needs to apply to both the latest version of the app
    and any previous version that is
    [still supported][supported-clients].
    For example, if the mobile app previously used a given feature
    and then stopped doing so, we can't remove the feature until
    about 12 months after the mobile release that stopped using it.
    (The mobile team lead makes removal decisions based on data
    the app stores provide about the distribution of versions).

  - Quickly check if the latest zulip/zulip-terminal might use the feature,
    and file an issue if it might. It's typically a quick `git grep`.
    We do not block API changes on terminal app compatibility.

  - Consider whether it's likely that any third-party
    integrations, bots, tools, or other clients
    might use the feature.
    Typically we figure they'll definitely use
    certain key endpoints like [/api/send-message][];
    won't use admin-only settings;
    and things in between are less clear.
    When in doubt, assume a feature might be used.
    Zulip Cloud maintainers have access to logs that can help determine
    to what extent an API endpoint is currently used by third-party code
    in that environment, but we have no access to similar data
    for self-hosted environments.

[supported-clients]: ../overview/release-lifecycle.md#server-and-client-app-compatibility
[/api/send-message]: https://zulip.com/api/send-message

### Making a change compatible

When an API change isn't automatically compatible
(as described in the preceding section),
we have to do some more work to make it compatible.

The fundamental strategy here is to make the change **opt-in**.
This means that existing clients, those unaware of the change,
don't see the change.

The basic way to make a change opt-in is to have the affected endpoint
take a new parameter that enables the change, defaulting to off.
For example, [`allow_empty_topic_name` on /api/get-messages][]

When an API change affects the content of events,
we need to use a variation on that approach:
we add one more flag to the [`client_capabilities`][] parameter
of [/api/register-queue][], again defaulting to off.
The resulting event queue then applies the given "client capability",
affecting all requests to [/api/get-events][] that use that queue.

When a change is opt-in
(through either of these ways or any other variation),
it incurs an ongoing complexity cost in the server codebase
because the server must continue to support the old form
as well as the new form.
For this reason it's good to eventually come back and
remove support for the old form. You should add a
`TODO/compatibility` marker in the server codebase detailing
the plan for compatibility code that you expect to be able to
delete when a given condition has occurred. You should review
several examples of this pattern using `git grep TODO/compat -A10`
before writing such a marker.

That removal is itself an API change, though,
so it needs to go through the process like any other change.

Clients can help reduce this maintenance cost for the server
implementation by promptly upgrading to request and properly handle
the new form of recently changed APIs. (Even if the client app team
doesn't have time to fully implement the new feature that motivated
the API change).

[`allow_empty_topic_name` on /api/get-messages]: https://zulip.com/api/get-messages#parameter-allow_empty_topic_name
[`client_capabilities`]: https://zulip.com/api/register-queue#parameter-client_capabilities
[/api/get-events]: https://zulip.com/api/get-events

## Clean APIs

Designing an API change cleanly isn't as immediately critical
as making sure it's compatible:
an API not being clean won't immediately cause anything to break.

It's valuable to the project, though, that most of our API
meets a fairly high standard of cleanliness and clarity.
(Not all of it; we've made some mistakes.)

This has helped us keep space for making more and more
API changes without boxing ourselves in.

It's also an essential ingredient in enabling the developers
of the Zulip mobile app to efficiently implement each new feature,
without having to reverse-engineer the server's behavior
or work around awkward quirks
that complicate a client's implementation.

Similarly, one of Zulip's selling points for users is that
our API lets users write custom tools that can do anything
the official clients can do.
For this promise to work out in practice,
it's important that the API be reasonably clear
and free of pitfalls.

Writing a clean API is a matter of taste, experience,
and engineering judgement,
and can't straightforwardly be codified.
With that in mind, though, here are some broad principles
and questions to ask when reviewing a proposed API change
for cleanliness and clarity:

- Think through what a client-side implementation of the feature
  (e.g., for web, or for mobile)
  would look like.
  Are there API revisions that would make that simpler or clearer?
  Should logic for the API feature be implemented in the
  server, the client, or both?

- Think through the proposed semantics of the new API.
  Make sure they make sense and seem like they'll solve
  the intended problem.

- Think through the proposed data structures,
  and the names of parameters, fields, and enum values.
  Make sure they're clear, they match the semantics,
  and they aren't likely to accidentally suggest a meaning
  that's different from the actual meaning.

- Think about possible future extensions of the API feature
  that is being implemented. Could the API design being
  proposed force us to make an incompatible change if we
  want to add a natural extension of the current feature?
  (For example: Some early API fields were implemented as
  tuples, rather than objects, and all of those resulted in
  painful migration work to replace the tuples with objects
  as additional fields were desired).

## API change process

The essential thing is that all API changes
are discussed and approved in the [#api design][] channel.
See [the description above](#api-change-process-in-short).

More details on the process are below.

### As a PR author

If you're the author of a PR, please go ahead and
start the [#api design][] thread yourself.
Then put a link to it in the PR description.

For any discussion that isn't specifically related to the API changes,
please use a different channel such as [#backend][]. (You can
cross-link, if a data model discussion has implications for the API,
for example).

Keeping [#api design][] focused is important for other participants
such as the mobile team, so that
they can be sure to follow the discussions on [#api design][]
that are about API changes and are important for them.

[#backend]: https://chat.zulip.org/#narrow/channel/3-backend

### As a PR reviewer

If you're reviewing a PR and it seems to make changes to the API,
check the PR description for a link to an [#api design][] thread.
If there isn't one already, ask about it in your review.
You can also start the thread yourself.

If you're reviewing a PR and it's near ready to merge,
check to see if the [#api design][] thread has concluded
with approval of a proposed change.
Check also that the PR's API changes match the agreed-on plan.
If the chat thread hasn't concluded, please post there
to try to bring it toward a conclusion.

### As an API reviewer

After an API change is approved on [#api design][],
the author on the server side prepares or revises a PR
to implement the change.

If you were involved in approving the API change —
and particularly if maintaining our API quality is
an important part of your work,
e.g., because you're the lead of the mobile team —
then it's helpful to review that PR for its API docs changes.
That means totally ignoring the code and reading only
`api_docs/` and `zerver/openapi/`.

- Depending on the author's skills and their experience with
  Zulip development, it's common for the draft docs to be
  unclear or inaccurate.
  Feedback on those is very helpful.

- Sometimes the draft docs reveal a misunderstanding or
  miscommunication about the API semantics that were agreed to.
  Those cases are important to catch.

### As a channel maintainer of [#api design][]

If you're one of the maintainers responsible for the
[#api design][] channel,
try to catch up on threads there each workday.

If a thread needs input from the system you work on
(mobile, web, server),
try to provide it or to identify someone to do so.

If the proposed changes look good from your perspective
but still need feedback from another perspective
(e.g., server/web vs. mobile),
try to make that clear, so the PR's author or reviewer
doesn't mistakenly think the changes are already approved. An example
remark might be:

> This looks good to me, but we need someone from the mobile team
> to confirm ...

Conversely, if all perspectives are either already represented
or you believe they're unnecessary for the particular change,
then say explicitly that the API changes are approved
so that the PR's author and reviewer know they can move forward.

Once an API change is approved,
consider filing issues to implement it for mobile and other clients.
(Or asking, on the thread, for someone else to file those.)
This is useful for high-priority changes in order to move quickly.
For most changes, we wait until the server PR has been merged
and a bot posts about it in [#api documentation][].

[#api documentation]: https://chat.zulip.org/#narrow/channel/412-api-documentation

### As the mobile team lead

If you're leading the mobile team, that probably means
you're a maintainer of the [#api design][] channel
and an API reviewer for most API changes.
See the corresponding subsections above.

After each API change is merged into the server,
a bot will post a new thread in [#api documentation][].
You should make sure you or someone else
replies to explicitly decide if there should be a mobile issue
to track making a corresponding change in the mobile app,
and files or updates such an issue if needed.
(See [#api documentation > new feature level: 454 @ 💬](https://chat.zulip.org/#narrow/channel/412-api-documentation/topic/new.20feature.20level.3A.20454/near/2360660).)
