# General User Guide Documentation

Our goal is for Zulip to have complete, high-quality user-appealing
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

When you write user-appealing documentation, keep in mind that most users
don't care about how the underlying code works; they simply want to know
how a feature works or how they can do something.

Think of writing user documentation as writing a recipe; you're trying to
direct your readers how to cook a dish while introducing them to the dish
itself, yet you shouldn't go into detail about the scientific processes that
allow you to cook your dish.

By keeping these thoughts in mind, you'll be able to write better
user guide documentation.

### Title

The title of your documentation should be a brief summary of your
documentation. Your title should be formatted as a heading by prepending
your title with a `#`.

The title of your documentation needs to be included under a fitting section
in `templates/zerver/help/sidebar.md` so users can access it from the user
documentation index.

### Introduction

By writing a brief introduction of what you will be discussing in your
documentation, users will gain a better understanding of your document. For
example, if you are writing about a feature, you could describe what the
feature allows users to do. Your introduction should be no longer than two
paragraphs.

### Directions

If you are guiding a user on how to perform a certain task in Zulip, it is
best to explain the process through a series of numbered steps. Your
documentation's goal is to direct users on how to do something so that they
achieve their goals. Thus, steps should be as detailed yet concise as
possible.

For example, if you tried to explain copying and pasting text, you could
describe it in the following steps:

```
1. Highlight the text you want to copy.

2. Press CTRL+C to copy the highlighted text.

3. Move your cursor to the location where you want to paste the text.

4. Press CTRL+V to paste the copied text.
```

You can continue steps with additional notes or instructions by breaking the
line and indenting the next line, which is especially useful for including
images within a single step.

```
1. Do something.

    You can also do this.
```

A general tip for breaking up a process is whenever a user interacts with
the Zulip UI (e.g.: click a button, refresh the page), a new step should be
created.

### Sections

If you are documenting multiple processes in your documentation, such as how
to perform a task by using several different features, you should
differentiate the processes by dividing them into sections using headings.
Like the title, your section headings should give a brief description of the
processes you describe.

All subsequent subsections should be appended with an increasing number of
`#`'s to make the headings smaller.

```
# Title

## Section 1

### Subsection 1

### Subsection 2

## Section 2

### Subsection 1
```

Always leave a blank line on either side of a section heading.

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

Images are often formatted as continuations of steps and must be indented on
a new line to be formatted this way.

### Icons

You can refer to features in the Zulip UI by referencing their names and
their [FontAwesome](http://fontawesome.io) (version 4.7.0) text icons within
parentheses. The source for the text icons is located in
`static/third/thirdparty-fonts.css`. **Note:** It is strongly recommended to use
the new base class `fa` instead of the older base class `icon-vector` when
specifying icons. In future we will be removing support for the icons with base
class `icon-vector`.

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
[main Zulip server repository](https://github.com/zulip/zulip). If you find
multiple instances of particular content in the documentation, you can
always create a new macro by adding a new file to that folder.

### **Organization settings** `{!admin.md!}` macro

* **About:** Links to the **Organization settings** documentation. Usually
preceded by a link to a particular section on the **Organization settings**
page.

* **Contents:**
    ```md
    tab of the [Organization settings](/help/edit-administrator-settings) page.
    ```

* **Example usage and rendering:**
    ```md
    1. Go to the [Organization settings](/#organization/organization-settings)
    {!admin.md!}
    ```
    ```md
    1. Go to the [Organization settings](/#organization/organization-settings) tab of the
    [Organization](/help/edit-administrator-settings) page.
    ```

### **Administrator only feature** `{!admin-only.md!}` macro

* **About:** Creates a note the feature discussed in the documentation is
only available to organization administrators. It should be placed
immediately after the title.

* **Contents:**
    ```md
    !!! warn ""
        **Note:** This feature can only be controlled by organization administrators.
    ```

* **Example usage and rendering:**
    ```md
    {!admin-only.md!}

    Follow the following steps to change who can join your stream by changing the stream's
    accessibility.
    ```
    ```md
    !!! warn ""
        **Note:** This feature can only be controlled by organization administrators.

    Follow the following steps to change who can join your stream by
    changing the stream's accessibility.
    ```

### **All streams** `{!all-streams.md!}` macro

* **About:** Explains how to view all streams in the organization on the
**Streams** page. Usually formatted as a tip and preceded by the
[**Streams** macro](#streams-subscriptions-md-macro) and the
[**Filter streams** macro](#filter-streams-filter-streams-md-macro).

* **Contents:**
    ```md
        If you wish to see streams that you aren't subscribed to, click on the
            **All streams** tab; the tab will turn gray upon doing so.
    ```

* **Example usage and rendering:**

    ```md
    {!subscriptions.md!}
    {!filter-streams.md!}
        !!! tip ""
        {!all-streams.md!}
    ```
    ```md
    1. [Find the relevant stream](/help/browse-and-join-streams#browse-streams) on the
    [Streams](/#streams) page. You can search for specific streams by entering the
    name of the stream in the **Filter streams** input.
        !!! tip ""
            If you wish to see streams that you aren't subscribed to, click on the
            **All streams** tab; the tab will turn gray upon doing so.
    ```

### **Down chevron** `{!down-chevron.md!}` macro

* **About:** Instructs readers to click on the down chevron (<i class="fa
fa-chevron-down"></i>) icon to reveal an actions dropdown; usually preceded by
an command, such as the [**Message actions**
macro](#message-actions-message-actions-md-macro).

* **Contents:**
    ```md
    down chevron (<i class="fa fa-chevron-down"></i>) icon to reveal an actions dropdown.
    ```

* **Example usage and rendering:**
    ```md
    {!message-actions.md!}
    {!down-chevron.md!}
    ```
    ```md
    1. Hover over a message to replace the message's timestamp with its message
    actions, represented by three icons. From the icons that appear, select the
    down chevron (<i class="fa fa-chevron-down"></i>) icon to reveal an actions dropdown.
    ```

### **Filter streams** `{!filter-streams.md!}` macro

* **About:** Explains how to search for specific streams in the
  **Streams** page using the **Filter streams** input. Usually preceded by
  the [**Streams** macro](#streams-subscriptions-md-macro).

* **Contents:**
    ```md
    You can search for specific streams by entering the name of the stream in
    the **Filter streams** input.
    ```

* **Example usage and rendering:**
    ```md
    {!subscriptions.md!}
    {!filter-streams.md!}
    ```
    ```md
    1. [Find the relevant stream](/help/browse-and-join-streams#browse-streams) on the
    [Streams](/#streams) page. You can search for specific streams by entering the
    name of the stream in the **Filter streams** input.
    ```

### **Message actions** `{!message-actions.md!}` macro

* **About:** Explains how to view the actions of message. Usually followed by an instruction
to click a specific icon, such as the [**Down chevron** macro](#down-chevron-down-chevron-md-macro).

* **Contents:**
    ```md
    1. Hover over a message to replace the message's timestamp with its message
    actions, represented by three icons. From the icons that appear, select the
    ```

* **Example usage and rendering:**
    ```md
    {!message-actions.md!}
    {!down-chevron.md!}
    ```
    ```md
    1. Hover over a message to replace the message's timestamp with its message
    actions, represented by three icons. From the icons that appear, select the
    down chevron (<i class="fa fa-chevron-down"></i>) icon to reveal an actions dropdown.
    ```

### **Save changes** `{!save-changes.md!}` macro

* **About:** Used in documentation that requests users to save their changes
by pressing the **Save changes** button. Usually followed by a phrase
describing the settings they modified.

* **Contents:**
    ```md
    1. Click on the **Save changes** button to save any changes you made to
    your
    ```

* **Example usage and rendering:**
    ```md
    {!save-changes.md!} notification settings.
    ```
    ```md
    1. Click on the **Save changes** button to save any changes you made to
    your notification settings.
    ```

### **Settings** `{!settings.md!}` macro

* **About:** Links to the **Edit Settings** documentation. Usually preceded by
a link to a particular section on the **Settings** page.

* **Contents:**
    ```md
    tab on the [Settings](/help/edit-settings) page.
    ```

* **Example usage and rendering:**
    ```md
    1. Go to the [Notifications](/#settings/notifications)
    {!settings.md!}
    ```
    ```md
    1. Go to the [Notifications](/#settings/notifications) tab on the
    [Settings](/help/edit-settings) page.
    ```

### **Stream actions** `{!stream-actions.md!}` macro

* **About:** Explains how to view the actions of stream. Usually followed by the an
instruction and the [**Down chevron** macro](#down-chevron-down-chevron-md-macro).

* **Contents:**
    ```md
    1. On the left sidebar in the **Streams** section, hover over a stream to reveal
    a down chevron (<i class="fa fa-chevron-down"></i>) icon to the right of
    the stream name.
    ```

* **Example usage and rendering:**
    ```md
    {!stream-actions.md!}

    1. Click on the {!down-chevron.md!}
    ```

    ```md
    1. On the left sidebar in the **Streams** section, hover over a stream to reveal
    a down chevron (<i class="fa fa-chevron-down"></i>) icon to the right of
    the stream name.

    2. Click on the down chevron (<i class="fa fa-chevron-down"></i>)
    icon to reveal an actions dropdown.
    ```

### **Stream settings** `{!stream-settings.md!}` macro

* **About:** Notifies readers about the changes in the
  **Streams** page when a stream is selected; usually followed
  by an instruction.

* **Contents:**
    ```md
    the right side of the [Streams](/#streams) page, labeled
    **Stream settings**, will now display the selected stream's settings.
    ```

* **Example usage and rendering:**
    ```md
    1. Click on the stream you want to edit; {!stream-settings.md!}
    ```
    ```md
    1. Click on the stream you want to edit; the right side of the
    [Streams](/#streams) page, labeled **Stream settings**, will
    now display the selected stream's settings.
    ```

### **Stream settings scroll** `{!stream-settings.md!}` macro

* **About:** Instructs readers to scroll down to a particular section on the
**Streams** page after making sure their cursors are hovering above the
**Streams Settings** section.

* **Contents:**
    ```md
    1. After making sure that your cursor is hovering over the **Streams Settings**
    section, scroll down to the
    ```

* **Example usage and rendering:**
    ```md
    {!stream-settings-scroll.md!} **Stream membership** section. This section
    shows the usernames and emails of all users that are currently subscribed to the
    selected stream.
    ```
    ```md
    1. After making sure that your cursor is hovering over the **Streams Settings**
    section, scroll down to the **Stream membership** section. This section
    shows the usernames and emails of all users that are currently subscribed to the
    selected stream.
    ```

### **Streams** `{!subscriptions.md!}` macro

* **About:** Used in documentation that direct users to the **Streams** page.
Often followed by the [**Filter streams** macro](#filter-streams-filter-streams-md-macro).

* **Contents:**
    ```md
    1. [Find the relevant stream](/help/browse-and-join-streams#browse-streams) on
    the [Streams](/#streams) page.
    ```

* **Example usage and rendering:**
    ```md
    {!subscriptions.md!}
    {!filter-streams.md!}
    ```
    ```md
    1. [Find the relevant stream](/help/browse-and-join-streams#browse-streams) on the
    [Streams](/#streams) page. You can search for specific streams by entering the
    name of the stream in the **Filter streams** input.
    ```


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

## Documentation template

Here is a template for writing user documentation that follows the
guidelines listed in this document. It demonstrates the proper formatting of
several features discussed above.

You can always look at previously-written documentation in the
`templates/zerver/help` folder as a reference for writing your
documentation.

```
# Title of documentation

This paragraph briefly summarizes the documentation. Please remember to
replace this paragraph with an appropriate description of the documentation.

## Writing documentation as a series of steps

1. This is the first step of the documentation.

    ![First step](/static/images/help/image1.png)

2. This is the second step of the documentation.

    Here's an additional note about the second step. Click on the star (<i
    class="fa fa-star-half-o"></i>) icon to learn more about it.

3. This is the third step of the documentation.

    !!! tip ""
        You can always add more steps to your documentation!

## Writing documentation to introduce a feature

If necessary, you can add another section to your documentation. Sections
can be used to differentiate different methods of performing a task or
describing a related task.

![Feature](../static/images/help/feature.png)

You can also conclude your documentation with some final notes.

!!! warn ""
    **Note:** This is only a documentation template; you can always deviate
    **from this template to suit your documentation needs.
```
