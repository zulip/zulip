# Writing help center articles

Our goal is for Zulip to have complete, high-quality
documentation about Zulip's features and how to perform certain tasks, such
as setting up an organization.

There are two types of help center documents: articles about specific features,
and a handful of longer guides. The feature articles serve a few different purposes:

- Feature discovery, for someone browsing the `/help/` page, and looking at
  the set of articles and guides.

- Public documentation of our feature set, for someone googling "can zulip do ..."

- Quick responses to support questions; if someone emails a Zulip admin
  asking "How do I change my name?", they can reply with a link to the doc.

- Feature explanations for new Zulip users and admins, especially for
  organization settings.

Zulip help center documentation is available under `/help/` on any Zulip server;
(e.g. <https://zulip.com/help/> or `http://localhost:9991/help/` in
the Zulip development environment). The help center documentation is not hosted
on ReadTheDocs, since Zulip supports running a server completely disconnected
from the Internet, and we'd like the documentation to be available in that
environment.

The source for help center documentation is the Markdown files under
`help/` in the [main Zulip server repository](https://github.com/zulip/zulip).
The file `foo.md` is automatically rendered by the `render_markdown_path`
function in `zerver/templatetags/app_filters.py` when the user accesses a URL
of the form `/help/foo`; with special cases for `/help/` going to `index.md`
and `/help/unknown_article` going to `missing.md` (with a 404 response).
Images are usually linked from `static/images/help/`.

This means that you can contribute to the Zulip help center documentation
by just adding to or editing the collection of Markdown files under
`help/...`. If you have the Zulip development environment set up, you simply
need to reload your browser on `http://localhost:9991/help/foo` to see the
latest version of `foo.md` rendered.

This system is designed to make writing and maintaining such documentation
highly efficient. We link to the docs extensively from the landing pages and
in-product, so it's important to keep the docs up to date.

## Guide to writing help center articles

Writing documentation is a different form of writing than most people have
experience with.

### Getting started

There are over 100 feature articles and longer guides in the
[Zulip help center](https://zulip.com/help/), so make the most of
the current documentation as a resource and guide as you begin.

- Use the list on [Zulip help center home](https://zulip.com/help/)
  to find the section of the docs (e.g. Preferences, Sending
  messages, Reading messages, etc.) that relates to the new feature
  you're documenting.

- Read through the existing articles in that section and pay attention
  to the [writing style](#writing-style) used, as well as any
  [Markdown features](#markdown-features) used to enhance the
  readability of the documentation.

- Should the feature you're documenting be added or merged into an
  existing article?

  - If so, you can locate that article in `help/` and start working
    on updating it with content about the new feature.

  - If not, choose an existing article to use as a template for your
    new article and make a list of which articles (or guides) would be
    good to link to in your new feature documentation.

Remember that real estate in the left sidebar is somewhat precious.
Minor features should rarely get their own article, and should instead
be merged into the existing help center documentation where appropriate.

If you are unsure about how and where to document the feature, you
can always ask in
[#documentation](https://chat.zulip.org/#narrow/stream/19-documentation)
on the [Zulip community server](https://zulip.com/development-community/).

### Updating an existing article

If the new feature you're documenting is a refinement on,
or related to, a feature that already has a dedicated help center
article, the information will be more useful and discoverable for
users as an addition to the existing article.

Here are some things to keep in mind when expanding and updating
existing help center articles:

- Maintain the format and [writing style](#writing-style) of the
  current article.

- Review the [Markdown features](#markdown-features) available and
  pay attention to the ones already utilized in the article.

- Think about where inline links to other help center documentation
  would be appropriate in the description of the feature. For example,
  your new feature might relate to general Zulip features like
  [keyboard shortcuts](https://zulip.com/help/keyboard-shortcuts)
  or [streams and topics](https://zulip.com/help/streams-and-topics).

- Make sure there is a **Related articles** section at the end
  of the article that again links to any help center documentation
  mentioned in the text or related to the feature.

If your updates to the existing article will change the name of the
markdown file, then see section below on [redirecting an existing
article](#redirecting-an-existing-article).

Creating robust and informative help center articles with good links
will allow users to navigate the help center much more effectively.

### Adding a new article

If the feature you're documenting needs a new article, here are some
things to keep in mind, in addition to the points made above for
updating existing documentation:

- Choose an existing article in the related section of the help
  documentation, and copy the format, wording, style, etc. as closely
  as you can.

- If the feature exists in other team chat products, check out their
  documentation for inspiration.

- Fewer words is better than more. Many Zulip users have English as a second
  language.

- Try to put yourself in the shoes of a new Zulip user. What would you want
  to know?

- Remember to explain the purpose of the feature and give context as well
  as instructions for how to use or enable it.

- The goal of user-facing documentation is not to be comprehensive. The goal
  is to give the right bits of information for the intended audience.

An anti-pattern is trying to make up for bad UX by adding help center
documentation. It's worth remembering that for most articles, almost 100% of
the users of the feature will never read the article. Instructions for
filling out forms, interacting with UI widgets (e.g. typeaheads), interacting
with modals, etc. should never go in the help center documentation.
In such cases, you may be able to fix the problem by adding text in-app,
where the user will see it as they are interacting with the feature.

### Redirecting an existing article

From time to time, we might want to rename an article in the help
center, or REST API documentation. This change will break incoming
links, including links in published Zulip blog posts, links in other
branches of the repository that haven't been rebased, and more
importantly links from previous versions of Zulip.

To fix these broken links, you can easily add a URL redirect in:
`zerver/lib/url_redirects.py`.

For help center documentation, once you've renamed the file in your
branch (e.g., `git mv path/to/foo.md path/to/bar.md`), go to
`url_redirects.py` and add a new `URLRedirect` to the
`HELP_DOCUMENTATION_REDIRECTS` list:

```python
HELP_DOCUMENTATION_REDIRECTS: List[URLRedirect] = [
    # Add URL redirects for help center documentation here:
    URLRedirect("/help/foo", "/help/bar"),
    ...
```

Note that you will also need to add redirects when you're deleting
a help center article and adding its content to an existing article
as a section. In that case, the new URL will include the new section
header: `URLRedirect("/help/foo", "/help/bar#new-section-header"),`.

For REST API documentation, you will either need to rename the file
as above, or you will need to update the endpoint's `operationId` in
`zerver/openapi/zulip.yaml`. Then, you would add a new `URLRedirect`
to the `API_DOCUMENTATION_REDIRECTS` list in `url_redirects.py`.

You should still check for references to the old URL in your branch
and replace those with the new URL (e.g., `git grep "/help/foo"`).
Updating section headers in existing help center articles does not
require adding a URL redirect, but you will need to update any
existing links to that article's section in your branch.

If you have the Zulip development environment set up, you can manually
test your changes by loading the old URL in your browser (e.g.,
`http://localhost:9991/help/foo`), and confirming that it redirects to
the new url (e.g., `http://localhost:9991/help/bar`).

There is also an automated test in `zerver/tests/test_urls.py` that
checks all the URL redirects, which you can run from the command line:

```console
./tools/test-backend zerver.tests.test_urls.URLRedirectTest
```

## Writing style

Below are some general style and writing conventions that should be used
as guidance when documenting Zulip's features.

### User interface

When you refer to the features in the Zulip UI, you should **bold** the
feature's name followed by the feature itself (e.g. **Settings** page,
**Change password** button, **Email** field). No quotation marks should be
used. Use **bold** for stream names, and quotation marks for topic names.

Keep in mind that the UI may change — don’t describe it in more detail than
is needed. In particular:

- Do not specify what the default configuration is. This might change in the
  future, or may even be different for different types of organizations.
- Do not list out the options the user is choosing from. Once the user finds the
  right menu in the UI, they'll be able to see the options. In some cases, we
  may describe the options in more detail outside of the instructions block.
- Never identify or refer to a button by its color. You _can_ describe its
  location.
- Use screenshots only when it's very difficult to get your point across without
  them.

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
produce when pressed (e.g. `R` and `Shift` + `R` rather than `r` and `R`).
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

If you're adding a tip to an article about a keyboard shortcut, you
should use the more specific keyboard [tip macro](#tips-and-warnings),
`!!! keyboard_tip ""`. In general, all keyboard shortcuts should be
documented on the [keyboard
shortcuts](https://zulip.com/help/keyboard-shortcuts) help center
article.

## Markdown features

Zulip's Markdown processor allows you to include several special features in
your documentation to help improve its readability:

- Since raw HTML is supported in Markdown, you can include arbitrary
  HTML/CSS in your documentation as needed.

- Code blocks allow you to highlight syntax, similar to
  [Zulip's own Markdown](https://zulip.com/help/format-your-message-using-markdown).

- Anchor tags can be used to link to headers in other documents.

- [Images](#images) of Zulip UI can be added to documentation, if needed.

- Inline [icons](#icons) are used to refer to features in the Zulip UI.

- Utilize [macros](#macros) to limit repeated content in the documentation.

- Create special highlight warning blocks using
  [tips and warnings](#tips-and-warnings).

- Format instructions with tabs using
  [Markdown tab switcher](#tab-switcher).

### Images

Images and screenshots should be included in help center documentation
only if they will help guide the user in how to do something (e.g. if
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

Images are often a part of a numbered step and must be indented four
spaces to be formatted correctly.

### Icons

You can refer to features in the Zulip UI by referencing their names
and their [FontAwesome](https://fontawesome.com/v4.7.0/) (version 4.7.0) text
icons within parentheses. **Note:** We have completed migrating away from older
base class `icon-vector` and have dropped support for it. We now only support
icons from [FontAwesome](https://fontawesome.com/v4.7.0/) (version 4.7.0) which
make use of `fa` as a base class.

- **cog** (<i class="fa fa-cog"></i>) icon:
  `**cog** (<i class="fa fa-cog"></i>) icon`
- **down chevron** (<i class="fa fa-chevron-down"></i>) icon:
  `**down chevron** (<i class="fa fa-chevron-down"></i>) icon`
- **eye** (<i class="fa fa-eye"></i>) icon:
  `**eye** (<i class="fa fa-eye"></i>) icon`
- **file** (<i class="fa fa-file-code-o"></i>) icon:
  `**file** (<i class="fa fa-file-code-o"></i>) icon`
- **filled star** (<i class="fa fa-star"></i>) icon:
  `**filled star** (<i class="fa fa-star"></i>) icon`
- **formatting** (<i class="fa fa-font"></i>) icon:
  `**formatting** (<i class="fa fa-font"></i>) icon`
- **menu** (<i class="fa fa-bars"></i>) icon:
  `**menu** (<i class="fa fa-bars"></i>) icon`
- **verflow** ( <i class="fa fa-ellipsis-v"></i> ) icon:
  `**overflow** ( <i class="fa fa-ellipsis-v"></i> ) icon`
- **paperclip** (<i class="fa fa-paperclip"></i>) icon:
  `**paperclip** (<i class="fa fa-paperclip"></i>) icon`
- **pencil** (<i class="fa fa-pencil"></i>) icon:
  `**pencil** (<i class="fa fa-pencil"></i>) icon`
- **pencil and paper** (<i class="fa fa-pencil-square-o"></i>) icon:
  `**pencil and paper** (<i class="fa fa-pencil-square-o"></i>) icon`
- **plus** (<i class="fa fa-plus"></i>) icon:
  `**plus** (<i class="fa fa-plus"></i>) icon`
- **smiley face** (<i class="fa fa-smile-o"></i>) icon:
  `**smiley face** (<i class="fa fa-smile-o"></i>) icon`
- **star** (<i class="fa fa-star-o"></i>) icon:
  `**star** (<i class="fa fa-star-o"></i>) icon`
- **trash** (<i class="fa fa-trash-o"></i>) icon:
  `**trash** (<i class="fa fa-trash-o"></i>) icon`
- **video-camera** (<i class="fa fa-video-camera"></i>) icon:
  `**video-camera** (<i class="fa fa-video-camera"></i>) icon`
- **x** (<i class="fa fa-times"></i>) icon:
  `**x** (<i class="fa fa-times"></i>) icon`

### Macros

**Macros** are elements in the format of `{!macro.md!}` that insert common
phrases and steps at the location of the macros. Macros help eliminate
repeated content in our documentation.

The source for macros is the Markdown files under `help/include` in the
[main Zulip server repository](https://github.com/zulip/zulip).

- **Administrator only feature** `{!admin-only.md!}`: Notes that the feature
  is only available to organization administrators.

- **Message actions** `{!message-actions.md!}`: First step to navigating to
  the on-hover message actions.

- **Message actions menu** `{!message-actions-menu.md!}`: Navigate to the
  message actions menu.

- **Save changes** `{!save-changes.md!}`: Save changes after modifying
  organization settings.

- **Stream actions** `{!channel-actions.md!}`: Navigate to the stream actions
  menu from the left sidebar.

- **Start composing** `{!start-composing.md!}`: Open the compose box.

### Tips and warnings

A **tip** is any suggestion for the user that is not part of the main set of
instructions. For instance, it may address a common problem users may
encounter while following the instructions, or point to an option for power
users.

```md
!!! tip ""

    If you've forgotten your password, see the
    [Change your password](/help/change-your-password) page for
    instructions on how to reset it.
```

A **keyboard tip** is a note for users to let them know that the same action
can also be accomplished via a [keyboard shortcut](#keyboard-shortcuts).

```md
!!! keyboard_tip ""

    Use <kbd>D</kbd> to bring up your list of drafts.
```

A **warning** is a note on what happens when there is some kind of problem.
Tips are more common than warnings.

```md
!!! warn ""

    **Note:** If you attempt to input a nonexistent stream name, an error
    message will appear.
```

All tips/warnings should appear inside tip/warning blocks. There
should be only one tip/warning inside each block, and they usually
should be formatted as a continuation of a numbered step.

### Tab switcher

Our Markdown processor supports easily creating a tab switcher widget
design to easily show the instructions for different
[platforms](https://zulip.com/help/logging-out) in help center articles,
languages in API docs, etc. To create a tab switcher, write:

```md
{start_tabs}
{tab|desktop-web}
# First tab's content
{tab|ios}
# Second tab's content
{tab|android}
# Third tab's content
{end_tabs}
```

The tab identifiers (e.g. `desktop-web` above) and their mappings to
the tabs' labels are declared in
[zerver/lib/markdown/tabbed_sections.py][tabbed-sections-code].

[tabbed-sections-code]: https://github.com/zulip/zulip/blob/main/zerver/lib/markdown/tabbed_sections.py

This widget can also be used just to create a nice box around a set of
instructions
([example](https://zulip.com/help/deactivate-your-account)) by
only declaring a single tab.
