# Getting your organization started with Zulip

This comprehensive guide explains in detail everything that the
administrator of a new Zulip organization needs to know to get off to a
great start with Zulip.

## Configure your Zulip organization

Review and potentially
[tweak the organization settings](/help/change-your-organization-settings)
to match your organization’s needs.

- Set a policy for who can join the organization.  If you’re setting
  up Zulip for your company, you can restrict new users to those from
  your company’s email domain.  You can also allow new users to join
  without being explicitly invited.

- Add an organization [icon](/help/create-your-organization-profile#change-your-organizations-avatar)
and [description](/help/create-your-organization-profile#change-your-organizations-description) for Zulip to
customize your login/registration pages as well as how your
organization appears in the desktop and mobile apps.

## Create streams

Most communication in Zulip happens in streams, and the streams you
create can help encourage types of conversations you’d like to see
happen in your organization. Streams are similar to chat rooms, email
lists, or channels in IRC or Slack, in that they determine who
receives a message. A few important notes:

- For small teams, it's often good to start with a small number of streams,
  and let the number of streams grow organically.
- You can use any character in stream names, including spaces and
  characters from non-Latin alphabets.
- You can
  [set the default streams](/help/set-default-streams-for-new-users)
  new organization members are subscribed to when they join.

The most important thing to do when naming your streams is to help
instill and support the culture you want to have in your organization.

- If your team is small, you can start with the default streams and
  iterate from there.
- For larger organizations, it can be helpful to have a consistent,
  documented naming scheme.  For example, help forums might have names
  like `help/git`, `help/javascript`, etc., so that they appear
  together in the left sidebar.
  [Slack’s article on channel naming](https://get.slack.help/hc/en-us/articles/217626408-Organize-and-name-channels)
  has a lengthy version of this advice.
- Add clear descriptions to your streams.

These articles contain great ideas for streams you might want to create
in your organization:

- [How the Recurse Center uses Zulip](https://www.recurse.com/blog/112-how-rc-uses-zulip)
- [The Zulip community](https://zulip.readthedocs.io/en/latest/contributing/chat-zulip-org.html#streams)

## Understanding topics

Zulip’s topics are life-changing, but it can take a bit of time for
everyone to learn how to use them effectively.  Expect there to be a
few rough edges at the beginning as people learn how to use topics
effectively.

- Topics play the role of the subject line in an email. They allow for
  long-running conversations, and make sure the discussion about the
  new logo design isn’t interrupted by lunch plans or scheduling for
  the offsite.
- Though the analogy to email subject lines is strong, topics in Zulip
  should be short, e.g. “logo” or “logo design”, not “Thoughts about
  the new logo design”.
- Topics really shine for asynchronous communication.
- When starting a new conversation, use a new topic, just like you
  would when starting an email thread.
- In the left sidebar, Zulip will by default show the 5 most recent
  topics in a stream as well as any topics with unread messages.  You
  don't need to do anything to "archive" old topics -- they will
  naturally disappear from recent topics when other topics replace
  them as the most recent.

## Familiarize yourself with Zulip’s featureset

As the administrator of your Zulip organization, you'll be the initial
expert teaching other users how to use Zulip.  It's valuable for you
to familiarize with Zulip’s featureset so you can point other users to
what they're looking for.

- Check out the keyboard shortcuts, message formatting, and search
  operators, available via the gear menu in the upper right of the
  app.
- Check out the settings, organization settings, and this
  documentation site to browse user and administration options.
- If you can't figure out how to do something important, ask
  [support@zulipchat.com](mailto:support@zulipchat.com) about the
  feature. It might already exist, and if not, we love hearing about
  what features people want!

## Invite users and onboard your community

- If you wish to delete messages before starting onboarding, hover over a
  message and click on the 'message actions' menu on the far right, then select
  'delete message'.
- Use the “#zulip” stream to share tips on how to use Zulip
  effectively.
- If you have an existing chat tool, make sure everyone knows that the
  team is switching, and why.  The team should commit to use Zulip
  exclusively **for at least a week** to make an effective trial;
  stragglers will result in everyone having a bad experience.
- Help your users get used to following topics and creating new ones
  when they start a new conversation.  It usually takes a few
  conversations to get used to topics, but once they do, they’ll never
  want to go back!  Using Zulip’s topic editing features to correct
  mistakes can help minimize confusion.

If your organization is large,
[Slack's guide](https://get.slack.help/hc/en-us/articles/115004378828-Onboard-your-company-to-Slack-)
for how to effectively roll out a new chat solution at a large company
in stages is great advice.

## Set up integrations

Zulip integrates directly with dozens of products, including all major
version control and issue tracking tools, and indirectly with hundreds
more through [Hubot](/integrations/doc/hubot), [Zapier](/integrations/doc/zapier),
and [IFTTT](/integrations/doc/ifttt).  Set up notifications for the products
you use!  A few recommendations:

- A product’s logo is a great choice of avatar for an integration with
  that product.
- For internal tools, find a cute icon for the avatar!
- Pay attention to how your integrations are configured.  If
  increasing activity means an integration becomes spammy, consider
  moving it to its own stream or configuring it to only send
  notifications for a subset of events.

## Bonus things to setup

- [Link to your Zulip instance](/help/join-zulip-chat-badge) from your
  GitHub or wiki page with a nice badge.
- [Automatically linkify](/help/add-a-custom-linkification-filter)
  issue numbers and commit IDs.
- [Write custom integrations](https://zulipchat.com/api/integration-guide)
  for your community’s unique tools.
- If your users primarily speak a language other than English,
  [set a default language for your organization](/help/change-the-default-language-for-your-organization).
- [Add custom emoji](/help/add-custom-emoji) for culturally important
  images, at the very least including your organization's logo.
- Send feedback to the Zulip development community!  We love hearing
  about problems (however minor) and feature ideas that could make
  Zulip even better.

## Managing your Zulip community

Here are some tips for improving the organization of your Zulip community over time:

- If users are confused about which stream to use for what, consider
  renaming streams to make the usage more obvious, and/or adding
  descriptions to the streams.
- If a stream has too much happening on it, especially very different
  things (for example, both short, important announcements and long,
  low-importance discussions), consider splitting it.  You can do this
  easily by copying the membership of the existing stream when
  creating a new stream.
- Periodically think about creating new streams for culture you want
  to foster in your organization.  For example, the Zulip development
  community has a “learning” stream where people post links to great
  resources they found, and the Recurse Center community has a
  “Victory” stream for celebrating success.
- Periodically garbage-collect streams that are no longer
  useful. Don’t worry — if you delete a stream, the old stream history
  is still searchable, and old links will still work.
- If you’re running your own Zulip server,
  [keep it up to date](https://zulip.readthedocs.io/en/latest/production/maintain-secure-upgrade.html)!
