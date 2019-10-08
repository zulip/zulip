# User documentation

Our goal is for Zulip to have complete, high-quality
documentation about Zulip's features and how to perform certain tasks, such
as setting up an organization.

There are two types of documents: articles about specific features, and a
handful of longer guides.

The feature articles serve a few different purposes:
* Feature discovery, for someone browsing the `/help` page, and looking at
  the set of titles.
* Public documentation of our featureset, for someone googling "can zulip do .."
* Canned responses to support questions; if someone emails a zulip admin
  asking "how do I change my name", they can reply with a link to the doc.
* Feature explanations for new Zulip users and admins, especially for
  organization settings.

This system is designed to make writing and maintaining such documentation
highly efficient. We link to the docs extensively from the landing pages and
in-product, so it's important to keep the docs up to date.

## Editing and testing

The user documentation is available under `/help/` on any Zulip server;
(e.g. <https://chat.zulip.org/help/> or `http://localhost:9991/help/` in
the Zulip development environment). The user documentation is not hosted on
ReadTheDocs, since Zulip supports running a server completely disconnected
from the Internet, and we'd like the documentation to be available in that
environment.

 The source for this user documentation is the Markdown files under
`templates/zerver/help/` in the
[main Zulip server repository](https://github.com/zulip/zulip). The file
`foo.md` is automatically rendered by the `render_markdown_path` function in
`zerver/templatetags/app_filters.py` when the user accesses a URL of the
form `/help/foo`; with special cases for `/help/` going to `index.md` and
`/help/unknown_article` going to `missing.md` (with a 404 response). Images
are usually linked from `static/images/help/`.

This means that you can contribute to the Zulip user documentation by just
adding to or editing the collection of markdown files under
`templates/zerver/help`.  If you have the Zulip development environment
setup, you simply need to reload your browser on
`http://localhost:9991/help/foo` to see the latest version of `foo.md`
rendered.

## Writing documentation

Writing documentation is a different form of writing than most people have
experience with.

Tips for adding a new article:

* Find an existing article in the same section of the help documentation,
  and copy the format, wording, style, etc as closely as you can.

* Fewer words is better than more. Many Zulip users have English as a second
  language.

* Try to put yourself in the shoes of a new Zulip user. What would you want
  to know?

* The goal of user-facing documentation is not to be comprehensive. The goal
  is to give the right bits of information for the intended audience.

### User interface

When you refer to the features in the Zulip UI, you should **bold** the
feature's name followed by the feature itself (e.g. **Settings** page,
**Change password** button, **Email** field). No quotation marks should be
used.

Keep in mind that the UI may change — don’t describe it in more detail than
is needed. **Never identify or refer to a button by its color.**

## Features

Zulip's Markdown processor allows you to include several special features in
your documentation to help improve its readibility:

* Since raw HTML is supported in Markdown, you can include arbitrary
HTML/CSS in your documentation as needed.
* Code blocks allow you to highlight syntax, similar to Zulip's own markdown.
* Anchor tags can be used to link to headers in other documents.
* [Images](#images) of Zulip UI can be added to documentation.
* Inline [icons](#icons) used to refer to features in the Zulip UI.
* You can utilize [macros](#macros) to limit repeated content in the
documentation.
* You can create special highlight warning blocks using
[tips and warnings](#tips-and-warnings).

### Images

Images and screenshots should be included in user documentation only
if it will help guide the user in how to do something (e.g. if the
image will make it much clearer which element on the page the user
should interact with).  For instance, an image of an element should
not be included if the element the user needs to interact with is the
only thing on the page, but images can be included to show the end
result of an interaction with the UI.

Using too many screenshots creates maintainability problems (we have
to update them every time the UI is changed) and also can make the
instructions for something simple look long and complicated.

When taking screenshots, the image should never include the whole
Zulip browser window in a screenshot; instead, it should only show
relevant parts of the app.  In addition, the screenshot should always
come *after* the text that describes it, never before.

Images are often a part of a numbered step and must be indented four spaces
to be formatted correctly.

### Icons

You can refer to features in the Zulip UI by referencing their names
and their [FontAwesome](https://fontawesome.com/v4.7.0/) (version 4.7.0) text
icons within parentheses. **Note:** We have completed migrating away from older
base class `icon-vector` and have dropped support for it. We now only support
icons from [FontAwesome](https://fontawesome.com/v4.7.0/) (version 4.7.0) which
make use of `fa` as a base class.

* cog (<i class="fa fa-cog"></i>) icon — `cog (<i
class="fa fa-cog"></i>) icon`
* down chevron (<i class="fa fa-chevron-down"></i>) icon —
`down chevron (<i class="fa fa-chevron-down"></i>) icon`
* eye (<i class="fa fa-eye"></i>) icon — `eye (<i
class="fa fa-eye"></i>) icon`
* file (<i class="fa fa-file-text-o"></i>) icon — `file (<i
class="fa fa-file-text-o"></i>) icon`
* filled star (<i class="fa fa-star"></i>) icon —
`filled star (<i class="fa fa-star"></i>) icon`
* formatting (<i class="fa fa-font"></i>) icon —
`formatting (<i class="fa fa-font"></i>) icon`
* menu (<i class="fa fa-bars"></i>) icon — `menu (<i
class="fa fa-bars"></i>) icon`
* overflow ( <i class="fa fa-ellipsis-v"></i> ) icon —
`overflow ( <i class="fa fa-ellipsis-v"></i> ) icon`
* paperclip (<i class="fa fa-paperclip"></i>) icon —
`paperclip (<i class="fa fa-paperclip"></i>) icon`
* pencil (<i class="fa fa-pencil"></i>) icon —
`pencil (<i class="fa fa-pencil"></i>) icon`
* pencil and paper (<i class="fa fa-pencil-square-o"></i>) icon —
`pencil and paper (<i class="fa fa-pencil-square-o"></i>) icon`
* plus (<i class="fa fa-plus"></i>) icon —
`plus (<i class="fa fa-plus"></i>) icon`
* smiley face (<i class="fa fa-smile-o"></i>) icon —
`smiley face (<i class="fa fa-smile-o"></i>) icon`
* star (<i class="fa fa-star-o"></i>) icon —
`star (<i class="fa fa-star-o"></i>) icon`
* trash (<i class="fa fa-trash-o"></i>) icon —
`trash (<i class="fa fa-trash-o"></i>) icon`
* video-camera (<i class="fa fa-video-camera"></i>) icon —
`video-camera (<i class="fa fa-video-camera"></i>) icon`
* x (<i class="fa fa-times"></i>) icon —
`x (<i class="fa fa-times"></i>) icon`

### Macros

**Macros** are elements in the format of `{!macro.md!}` that insert common
phrases and steps at the location of the macros. Macros help eliminate
repeated content in our documentation.

The source for macros is the Markdown files under
`templates/zerver/help/include` in the
[main Zulip server repository](https://github.com/zulip/zulip).

* **Administrator only feature** `{!admin-only.md!}`: Notes that the feature
  is only available to organization administrators.

* **Message actions** `{!message-actions.md!}`: First step to navigating to
  the on-hover message actions.

* **Message actions menu** `{!message-actions-menu.md!}`: Navigate to the
  message actions menu.

* **Save changes** `{!save-changes.md!}`: Save changes after modifying
  organization settings.

* **Stream actions** `{!stream-actions.md!}`: Navigate to the stream actions
  menu from the left sidebar.

* **Start composing** `{!start-composing.md!}`: Open the compose box.

### Tips and warnings

A **tip** is any suggestion for the user that is not part of the main set of
instructions. For instance, it may address a common problem users may
encounter while following the instructions, or point to an option for power
users.

```
!!! tip ""
    If you've forgotten your password, see the
    [Change your password](/help/change-your-password) page for
    instructions on how to reset it.
```

A **warning** is a note on what happens when there is some kind of problem.
Tips are more common than warnings.

```
!!! warn ""
    **Note:** If you attempt to input a nonexistent stream name, an error
    message will appear.
```

All tips/warnings should appear inside tip/warning blocks. There should be
only one tip/warning inside each block.They usually be formatted as a
continuation of a numbered step.
