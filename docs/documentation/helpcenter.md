# Writing help center articles

Our goal is for Zulip to have complete, high-quality
documentation about Zulip's features and key workflows, such
as setting up an organization.

There are two types of help center documents: articles about specific features,
and a handful of longer guides. We aim to have comprehensive onboarding guides,
plus a select handful of guides for administrators and power users. Our goal is
to document all the features of the app and associated key workflows.

The feature articles that make up the bulk of help center content serve many
purposes:

- Feature and workflow explanations for Zulip users and admins, including
  specific instructions and tips on when the feature would be useful. For
  complex settings (e.g., permissions), detailed explanations of how the feature
  works.

- Feature discovery, for someone browsing the help center, and looking at
  the set of articles and guides.

- Public documentation of our feature set for search engine and LLM users.

- Quick responses to support questions; if someone emails a Zulip admin
  asking "How do I change my name?", they can reply with a link to the doc.

- A reference to link to any time we mention the feature (e.g., in a Zulip
  update, on the Zulip website, in a blog post, etc.), for anyone who'd like
  more detail.

- Reference links from the Zulip app (e.g., for complex settings).

It's important to keep the docs up to date. We should update the help center as
needed whenever a feature is added or changed.

## Getting started

There are over 100 feature articles and longer guides in the
[Zulip help center](https://zulip.com/help/), so make the most of
the current documentation as a resource and guide as you begin.

- Use the left sidebar in the help center documentation to find the
  section of the docs (e.g., Preferences, Sending messages, Reading
  messages, etc.) that relates to the new feature you're documenting.

- Read through the existing articles in that section and pay attention
  to the [writing style](#writing-style) used, as well as any
  [features and components](#mdx-features-and-custom-zulip-components)
  used to enhance the readability of the documentation.

If you aren't sure how something should be documented, the
[#documentation](https://chat.zulip.org/#narrow/channel/19-documentation)
channel in the [Zulip development
community](https://zulip.com/development-community/) is a great place to get
help.

## Structure of a feature article

The general structure of a feature article is:

1. [Introduction](#introduction)
1. One or more [sections with instructions](#instructions-section)
1. [Related articles](#related-articles)

### Introduction

This is the part of the article that requires the most thought and understanding
of context. It should generally (often in roughly this order):

1. Explain briefly **what the feature does** for the user (but not how to activate it).
1. Give some **guidance** on when someone might want to use this feature, perhaps
   with specific examples.
1. **Explain more precisely** what the feature does, if there are important
   points to note. Are there any details that the user may feel uncertainty
   about that should be cleared up?
1. Note any **limitations**, like organization permissions settings that could disable this feature.
1. Briefly describe other features that are good **alternatives** for related workflows.

For example, the intro to the [article on moving messages to another
topic](https://github.com/zulip/zulip/blob/8ddc7bee008f7e8d13cbe0b5ec4d1e1eb2333a9d/starlight_help/src/content/docs/move-content-to-another-topic.mdx?plain=1)
follows this structure:

1. **What the feature does**:
   > Zulip makes it possible to move messages between topics.
1. **Guidance**:
   > This is useful for keeping messages organized when there is a digression,
   > or the discussion shifts from the original topic.
1. **Alternatives**:
   > You can also [rename a topic](https://zulip.com/help/rename-a-topic).
1. **Explain more precisely**:
   > When messages are moved, Zulip's [permanent links to messages in
   > context](https://zulip.com/help/link-to-a-message-or-conversation#get-a-link-to-a-specific-message)
   > will automatically redirect to the new location of the message. [Muted
   > topics](https://zulip.com/help/mute-a-topic) are automatically migrated when
   > an entire topic is moved.
1. **Limitations**:
   > Organization administrators can
   > [configure](https://zulip.com/help/restrict-moving-messages) who is allowed to move
   > messages.

You can see that the structure has some flexibility, but all the key points are
succinctly covered.

To write a good introduction, you may need to reread the issue that was fixed
and any user comments on the issue, and to skim any discussion around the
feature for relevant context.

### Instructions section

If the context for the feature is fully covered in the intro, a simple
subsection heading plus instructions works well. As described in detail at the
bottom of this article, be sure to use the standard help center
components/macros. Refer to other parts of the article you're working on, or
related articles (e.g., another setting in the same settings section).

Be sure to include a **Mobile** instructions tab if the feature is supported on
mobile. You can use a stub **Mobile** tab if we have an issue for it, but it's
not yet implemented.

When there are multiple ways to access a feature that are worth noting, label
tabs by the broad-level location of where the feature is accessed from (e.g.,
"Left sidebar"). We always document how to get to a setting via the settings UI,
even if there's a handy alternative. The most convenient method should be in the
first tab.

For a single set of desktop/web app instructions, use the "Desktop/Web" tab
label. We generally add this tab label for user features even if there are no
other tabs to add, but don't do so for admin features. The vast majority
of settings aren't available on mobile, so admins can easily infer that we're
referring to the desktop/web app.

In longer articles, the introduction might not cover everything. In that case,
we might add an introduction to an instructions section, with a similar
structure to article intros. Some caveats and alternatives can appear after the
instructions, but the most important content should precede them.

Be sure to document any keyboard shortcuts (generally inside the instructions
block).

### Related articles

What articles is the reader most likely to be interested in?

- Articles already linked to above are good candidates, but often not all of
  them will feel sufficiently relevant. For example, you don't need to link to
  articles that were linked to earlier just as a reference on some view or part
  of the UI that was mentioned.
- Articles about features that support related workflows.
- For a permission setting, the article that explains the feature (and conversely).
- Articles that go deeper into the same part of the app.
- For onboarding features, articles about features you might use around the same time.

Consider the reader -- in the context of this article, are they an end user or
an admin? Admin articles will primarily link to other admin articles, and
end-user articles to other end-user articles.

## What the help center _isn't_ for

An anti-pattern is trying to make up for bad UX by adding help center
documentation. When writing documentation, try to pay attention to whether
something feels hard to explain. It's a sign that there may be a product UX
problem to fix here. Are there ways to change UI strings or workflows that would
make the feature easier to document? That could be a good product direction to
explore.

It's worth remembering that for most articles, almost 100% of
the users of the feature will never read the article. Instructions for
filling out forms, interacting with UI widgets (e.g., typeaheads), interacting
with modals, etc. should never go in the help center documentation.
In such cases, you may be able to fix the problem by adding text in-app,
where the user will see it as they are interacting with the feature.

## Adding and updating articles

Should the feature you're documenting be added or merged into an existing
article?

Real estate in the left sidebar is somewhat precious.
Minor features should rarely get their own article, and should instead
be merged into the existing help center documentation where appropriate.

If the new feature you're documenting is a refinement on,
or related to, a feature that already has a dedicated help center
article, the information will be more useful and discoverable for
users as an addition to the existing article.

Permissions settings have a different target audience (administrators) than the
feature they control, and thus often get their own article (with cross-links).

### Updating an existing article

Here are some things to keep in mind when expanding and updating
existing help center articles:

- If you're repeating content, consider moving it to an /include file in a prep
  commit, for maintainability.
- While you're there, check for other updates: any new features the article
  should link to? outdated writing patterns? icons we missed updating? mobile
  instructions that need to be added? related articles you looked at that were
  missing reference links to this one? etc.

If your updates to the existing article will change the name of the
markdown file, then see section below on [redirecting an existing
article](#redirecting-an-existing-article). We're generally OK with the URL
being a bit off from the current article title, as long as it still makes sense
given the current content.

### Adding a new article

It's often easiest to get started by choosing an existing article to use as a
template for your new article (usually a similar feature in the same sidebar
section). You can match its format, wording, style, etc. If
you decide _not_ to follow its pattern, consider whether the article you're
using as a template should itself be updated.

Consider what articles (feature articles and guides) might need to link to the
article you're adding (see [related articles tips](#related-articles)). For
major new features, take a look at `/features` and other parts of the website
(e.g, `/for/business`) for potential updates to make.

If the feature exists in other team chat products, consider checking their
documentation for inspiration (but each app has its own documentation style).

## Writing style

Aim for a clear, specific, and succinct writing style. Remember that a wide
variety of users may be reading the article, including non-native English
speakers.

Avoid technical vocabulary and jargon wherever possible. It might be fine and
unavoidable in, e.g., explanations of linkifier details. But strongly avoid it
in, e.g., an introduction to a general user article. Remember that some terms
that feel familiar to you as perhaps an engineer, and someone who
specifically develops Zulip at that, may not be in common use.

### User interface

When you refer to the features in the Zulip UI, you should **bold** the
feature's name followed by the feature itself (e.g., **Settings** page,
**Change password** button, **Email** field). No quotation marks should be
used. Use **bold** for channel names, and quotation marks for topic names.

It's important to use consistent terminology for each UI element — doing
otherwise can be quite confusing to the reader. If you aren't quite sure what to
call something, check by finding another article that you expect to mention the
same part of the UI, or an analogous one.

Keep in mind that the UI may change — don’t describe it in more detail than
is needed. Beyond requiring more frequent updates, overly specific descriptions
are hard to maintain because nobody is likely to realize that the help center
needs to be updated when purely visual changes are made. In particular:

- Do not specify what the default configuration is. This might change in the
  future, or may even be different for different types of organizations.
- Do not list out the options the user is choosing from. Once the user finds the
  right menu in the UI, they'll be able to see the options. In some cases, we
  may describe the options in more detail outside of the instructions block.
- Never identify or refer to a button by its color. You _can_ describe its
  location.
- Use screenshots only when it's very difficult to get your point across without
  them.

We don't describe the UI just of the sake of describing it --- UI elements are
mentioned in the service of helping the user figure out how to take the actions
they need to take.

### Voice

Do not use `we` to refer to Zulip or its creators; for example, "Zulip also
allows ...", rather than "we also allow ...". On the other hand, `you` is ok
and used liberally.

### Keyboard shortcuts

Surround each keyboard key in the shortcut with `<kbd>` HTML element start and
end tags (e.g., `<kbd>Enter</kbd>` or `<kbd>R</kbd>`).

For shortcuts with more than one key, add a plus sign (+) surrounded by spaces
in between the keys (e.g., `<kbd>Ctrl</kbd> + <kbd>K</kbd>`). Any shortcut for
an arrow key (↑, ↓, ←, →) will also need the `"arrow-key"` CSS class included
in the `<kbd>` start tag (e.g., ` <kbd class="arrow-key">↑</kbd>`).

Use the labels one sees on the actual keyboard rather than the letter they
produce when pressed (e.g., `R` and `Shift` + `R` rather than `r` and `R`).
For symbols, such as `?` or `@`, that are produced through key combinations that
change depending on the user's keyboard layout, you should use the symbol as it
appears on a keyboard instead of any specific combination of keys.

Use non-Mac keyboard keys; for example `Enter`, instead of `Return`. Zulip will
automatically translate non-Mac keys to the Mac versions for users with a Mac
user agent. If you want to confirm that your documentation is rendering Mac keys
correctly when writing documentation in Windows or Linux, you can temporarily
change `has_mac_keyboard` in `/web/src/common.ts` to always return `True`.
Then when you view your documentation changes in the development environment,
the keyboard shortcuts should be rendered with Mac keys where appropriate.

If you're adding a tip to an article about a keyboard shortcut, you should
use the more specific [keyboard tip](#asides) component. In general, all
keyboard shortcuts should be documented on the [keyboard
shortcuts](https://zulip.com/help/keyboard-shortcuts) help center
article.

### Images

Images and screenshots should be included in help center documentation
_only_ if they will help guide the user in how to do something (e.g., if
the image will make it much clearer which element on the page the user
should interact with). For instance, an image of an element should
not be included if the element the user needs to interact with is the
only thing on the page, but images can be included to show the end
result of an interaction with the UI.

Using too many screenshots creates maintainability problems (we have
to update them every time the UI is changed) and also can make the
instructions for something simple look long and complicated.

When taking screenshots, the image should never include the whole
Zulip browser window in a screenshot; instead, it should only show
relevant parts of the app. In addition, the screenshot should always
come _after_ the text that describes it, never before.

Images used in the help center can be found at `starlight_help/src/images`.

## Viewing and updating help center articles

The help center is built with [@astro/starlight](https://starlight.astro.build/).
Starlight is a full-featured documentation theme built on top of the
[Astro](https://astro.build/) framework. Astro is a web framework designed
for content driven websites. The content for the help center articles are
[MDX](https://mdxjs.com/) files, which live at `starlight_help/src/content/docs`
in the [main Zulip server repository](https://github.com/zulip/zulip).
Images are usually linked from `starlight_help/src/images`.

Zulip help center documentation is available under `/help/` on any Zulip server;
(e.g., <https://zulip.com/help/> or `http://localhost:9991/help/` in
the Zulip development environment). The help center documentation is not hosted
on ReadTheDocs, since Zulip supports running a server completely disconnected
from the Internet, and we'd like the documentation to be available in that
environment.

This means that you can contribute to the Zulip help center documentation by
just adding to or editing the collection of MDX files under
`starlight_help/src/content/docs`. To add a help center article, create a new
file in `starlight_help/src/content/docs/`, and add a sidebar link to it in
`starlight_help/astro.config.mjs`.

If you have the Zulip development environment set up, you simply need to reload
your browser on `http://localhost:9991/help/foo` to see the latest version of
`foo.mdx` rendered.

This system is designed to make writing and maintaining such documentation
highly efficient.

## MDX features and custom Zulip components

MDX supports standard markdown syntax. Some useful markdown features to
remember when writing help center documentation are:

- Since raw HTML is supported in Markdown, you can include arbitrary
  HTML/CSS in your documentation as needed.

- Code blocks allow you to highlight syntax, similar to
  [Zulip's own Markdown](https://zulip.com/help/format-your-message-using-markdown).

- Anchor tags can be used to link to headers in other documents.

Additionally, there are some useful MDX components implemented and used
throughout the help center documentation:

- [Icon](#icons) components allow documentation to use the exact icons
  for a button or link that is used in the Zulip UI.

- [Include files](#include-files) allow us to reuse repeated content
  in the documentation.

- Our custom [Aside](#asides) components create special highlighted
  information and warning blocks for tips, keyboard shortcuts, and the
  like.

- Instructions can be formatted with [Tab](#tabs),
  [Steps/FlattenSteps](#steps-and-flattenedsteps) and
  [NavigationSteps](#navigationsteps) components.

### Icons

See [icons documentation](../subsystems/icons.md). Icons should always be
referred to with their in-app tooltip or a brief action name, _not_ the
name of the icon in the code.

When using these icons in an MDX file, they act as any other component:

```
import SquarePlusIcon from "~icons/zulip-icon/square-plus"

Click the **new topic** (<SquarePlusIcon />) button next to the name of the channel.
```

For the import statement, the icon component should be named as the camel
case of the icon name, with any dashes removed, followed by `Icon`, e.g.,
in the example above `square-plus` is imported as `SquarePlusIcon`.

### Include files

You can include any file inside another MDX file as a regular import, which
helps to eliminate repeated content in our documentation.

All our include files live at `starlight_help/src/content/docs/include`,
and can be imported and used as a regular component:

```
import AdminOnly from "./include/_AdminOnly.mdx";

<AdminOnly />
```

If you're adding a new include file, make sure to have an underscore at the
beginning of the file name as that ensures the file won't be considered a
standalone article in the help center.

A lot of our include files are list macros, i.e., they are partial lists
that are part of bigger lists. When the partial list is an ordered list,
it needs to be wrapped in a [FlattenedSteps](#steps-and-flattenedsteps)
component.

We recommend avoiding having any h2 or h3 headers (`##`, `###`) in an
include file because, when the file is imported into a help center article,
those headings will not be rendered in the "On this page" outline in the
right sidebar.

If it is necessary to have headers in the include file content, then the
workaround for having them rendered in the right sidebar is to insert the
same headers into any file where you are importing and using that include
file. In the example below, we add the two h3 headers from the include file so
that they are rendered in the right sidebar:

```
import AutomaticallyFollowTopics from "./include/_AutomaticallyFollowTopics.mdx";

<AutomaticallyFollowTopics>
  ### Follow topics you start or participate in

  ### Follow topics where you are mentioned
</AutomaticallyFollowTopics>
```

### Asides

We have customized aside components that are used for tips, warnings and
keyboard tips in the help center.

A **tip** is any suggestion for the user that is not part of the main set
of instructions. For instance, it may address a common problem users may
encounter while following the instructions, or point to an option for power
users.

```
import ZulipTip from "../../components/ZulipTip.astro";

<ZulipTip>
  The app will update automatically to future versions.
</ZulipTip>
```

A **keyboard tip** is a note for users to let them know that the same action
can also be accomplished via a [keyboard shortcut](#keyboard-shortcuts).

```
import KeyboardTip from "../../components/KeyboardTip.astro";

<KeyboardTip>
  You can also use <kbd>?</kbd> to open the keyboard shortcuts reference.
</KeyboardTip>
```

A **warning** is a note on what happens when there is some kind of problem.
Tips are more common than warnings.

```
import ZulipNote from "../../components/ZulipNote.astro";

<ZulipNote>
  This feature is only available to organization owners and administrators.
</ZulipNote>
```

There should be only one tip/warning inside each component. They usually
should be formatted as a continuation of a numbered step, if they are in
an ordered list.

You can find the code for these custom aside components at
`starlight_help/src/components`.

### Tabs

There are built-in [starlight/astro `Tab` and `TabItem`
components](https://starlight.astro.build/components/tabs/) for creating
tabbed instructions:

```
import {Steps, TabItem, Tabs} from "@astrojs/starlight/components";

import FlattenedSteps from "../../components/FlattenedSteps.astro";

import MobileSwitchAccount from "./include/_MobileSwitchAccount.mdx";

<Tabs>
  <TabItem label="Mobile">
    <FlattenedSteps>
      <MobileSwitchAccount />

      1. Tap **Add new account**.
      1. Enter the Zulip URL of the organization, and tap **Continue**.
      1. Follow the on-screen instructions.
    </FlattenedSteps>
  </TabItem>

  <TabItem label="Web">
    <Steps>
      1. Go to the Zulip URL of the organization.
      1. Follow the on-screen instructions.
    </Steps>
  </TabItem>
</Tabs>
```

The above example has instructions for logging in for the mobile app
and the web app. Make sure you add a label for each `TabItem`.

#### Steps and FlattenedSteps

If you don't need multiple tabs, or a tabbed label, for your instructions,
then you can just wrap the ordered list of instructions in a [`Steps`
component](https://starlight.astro.build/components/steps/):

```
import {Steps} from "@astrojs/starlight/components";

<Steps>
  1. Go to the Zulip URL of the organization.
  1. Follow the on-screen instructions.
</Steps>
```

If you have an ordered list of instructions with a portion of the list in
an [include file](#include-files), then you need to wrap the instructions
in a `FlattenedSteps` component, so that the instructions are numbered
correctly when rendered (e.g., `1.`, `2.`, `3.`, `4.`, etc.):

```
import FlattenedSteps from "../../components/FlattenedSteps.astro";

import MobileSwitchAccount from "./include/_MobileSwitchAccount.mdx";

<FlattenedSteps>
  <MobileSwitchAccount />

  1. Tap **Add new account**.
  1. Enter the Zulip URL of the organization, and tap **Continue**.
  1. Follow the on-screen instructions.
</FlattenedSteps>
```

#### NavigationSteps

Many instructions begin with the same set of steps, some of which can have
relative links that directly go to the logged in session for the Zulip
organization of the user reading the documentation. For these partial
instruction lists, we use a custom `NavigationSteps` component, which needs
to be wrapped in a `FlattenedSteps` component ([see above](#steps-and-flattenedsteps)).

```
import NavigationSteps from "../../components/NavigationSteps.astro";

<FlattenedSteps>
  <NavigationSteps target="settings/organization-permissions" />

  1. Under **Joining the organization**, toggle **Invitations are required for
     joining this organization**.

  <SaveChanges />
</FlattenedSteps>
```

Each `NavigationStep` has a `target`, which can be one of two forms:

- Settings: `settings/{setting_key}`
- Relative: `relative/{link_type}/{key}`

The settings targets are for instructions that navigate to a section in
either the personal or organization settings overlay in the web app.

The relative targets are for instructions that navigate from the gear or
help menus to a particular location in the web app.

See `starlight_help/src/components/NavigationSteps.astro` for what values
for settings and relative targets are currently implemented.

You can find the code for any custom components used in the help center at:
`starlight_help/src/components`.

## Redirecting an existing article

From time to time, we might want to rename an article in the help
center. This change will break incoming links, including links in
published Zulip blog posts, links in other branches of the repository
that haven't been rebased, and more importantly links from previous
versions of Zulip.

To fix these broken links, you can easily add a URL redirect in:
`starlight_help/astro.config.mjs`.

For a help center article, once you've renamed the file in your
branch (e.g., `git mv path/to/foo.mdx path/to/bar.mdx`), go to
`astro.config.mjs` and add a new line to the `redirects` property:

```
    // Redirects in astro are just directories with index.html inside
    // them doing the redirect we define in the value. The base of
    // /help/ will apply to the keys in the list below but we will
    // have to prepend /help/ in the redirect URL.
    redirects: {
        "pm-mention-alert-notifications": "/help/dm-mention-alert-notifications",
    ...
```

Note that you will also need to add redirects when you're deleting
a help center article and adding its content to an existing article
as a section. In that case, the new URL will include the new section
header:

```
"add-an-alert-word": "/help/dm-mention-alert-notifications#alert-words"
```

You should still check for references to the old URL in your branch
and replace those with the new URL (e.g., `git grep "/help/foo"`).
One exception to this are links with the old URL that were included
in the content of `zulip_update_announcements`, which can be found
in `zerver/lib/zulip_update_announcements.py`. It's preferable to
have the source code accurately reflect what was sent to users in
those [Zulip update announcements][help-zulip-updates], so these
should not be replaced with the new URL.

Updating section headers in existing help center articles does not
require adding a URL redirect, but you will need to update any
existing links to that article's section in your branch.

You can manually test your changes in the dev environment by loading the old URL
in your browser (e.g., `http://localhost:9991/help/foo`), and confirming that it
redirects to the new URL (e.g., `http://localhost:9991/help/bar`).

[help-zulip-updates]: https://zulip.com/help/configure-automated-notices#zulip-update-announcements
