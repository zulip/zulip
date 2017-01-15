# Documentation

Zulip has three major documentation systems:

* Developer and sysadmin documentation: Documentation for people
  actually interacting with the Zulip codebase (either by developing
  it or installing it), and written in Markdown.

* Core website documentation: Complete webpages for complex topics,
  written in HTML, JavaScript, and CSS (using the Django templating
  system).  These roughly correspond to the documentation someone
  might look at when deciding whether to use Zulip.  We don't expect
  to ever have more than about 10 pages written using this system.

* General user documentation: Our scalable system for documenting
  Zulip's huge collection of specific features without a lot of
  overhead or duplicated code/syntax, written in Markdown.  We expect
  to eventually have around 100 pages written using this system.  The
  target audience for this system is individual Zulip users.

These three systems are documented in detail below.

## Developer and sysadmin documentation

What you are reading right now is part of the collection of
documentation targeted at developers and people running their own
Zulip servers.  These docs are written in
[Commonmark Markdown](http://commonmark.org/) with a small bit of rST.
We've chosen Markdown because it is
[easy to write](http://commonmark.org/help).  The source for Zulip's
developer documentation is at `docs/` in the Zulip git repository, and
they are served in production at
[zulip.readthedocs.io](https://zulip.readthedocs.io/en/latest/).

If you want to build the developer documentation locally (e.g. to test
your changes), the dependencies are automatically installed as part of
Zulip development environment provisioning, and you can build the
documentation using:

```
cd docs/
make html
```

and then opening `file:///path/to/zulip/docs/_build/html/index.html` in
your browser (you can also use e.g. `firefox
docs/_build/html/index.html` from the root of your Zulip checkout).

If you are adding a new page to the table of contents, you will want
to modify `docs/index.rst` and run `make clean` before `make html`, so
that other docs besides your new one also get the new entry in the
table of contents.

You can also usually test your changes by pushing a branch to GitHub
and looking at the content on the GitHub web UI, since GitHub renders
Markdown, though that won't be as faithful as the `make html`
approach.

When editing dependencies for the Zulip documentation, you should edit
`requirements/docs.txt` (which is used by ReadTheDocs to build the
Zulip developer documentation, without installing all of Zulip's
dependencies).

## Core website documentation

Zulip has around 10 HTML documentation pages under `templates/zerver`
for specific major topics, like the features list, client apps,
integrations, hotkeys, API bindings, etc.  These documents often have
somewhat complex HTML and JavaScript, without a great deal of common
pattern between them other than inheriting from the `portico.html`
template.  We generally avoid adding new pages to this collection
unless there's a good reason, but we don't intend to migrate them,
either, since this system gives us the flexibility to express these
important elements of the product clearly.

## General user documentation

Our goal is for Zulip to have complete, high-quality user-facing
documentation about how to use every feature and how to do common
tasks (like setting up a new Zulip organization well).  This system is
designed to make writing and maintaining such documentation highly
efficient.

The user documentation is available under `/help/` on any Zulip
server;
(e.g. [https://chat.zulip.org/help/](https://chat.zulip.org/help/) or
`http://localhost:9991/help/` in the Zulip development environment).
The user documentation is not hosted on ReadTheDocs, since Zulip
supports running a server completely disconnected from the Internet,
and we'd like the documentation to be available in that environment.

The source for this user documentation is the Markdown files under
`templates/zerver/help/` in the
[main Zulip server repository](https://github.com/zulip/zulip).  The
file `foo.md` is automatically rendered by the `render_markdown_path`
function in `zerver/templatetags/app_filters.py` when the user
accesses a URL of the form `/help/foo`; with special cases for
`/help/` going to `index.md` and `/help/unknown_article` going to
`missing.md` (with a 404 response).  Images are usually linked from
`static/images/help/`.

This means that you can contribute to the Zulip user documentation by
just adding to or editing the collection of markdown files under
`templates/zerver/help`.  If you have the Zulip development
environment setup, you simply need to reload your browser on
`http://localhost:9991/help/foo` to see the latest version of `foo.md`
rendered.

Since raw HTML is supported in Markdown, you can include arbitrary
HTML in your documentation in order to do fancy things like
highlighting an important aspect of your code.  We'll likely add a
library of common components over time, which will be documented
below.

### Supported features

* All the usual features of Markdown with raw HTML enabled so you can
  do custom things with HTML/CSS as needed. The goal is to make
  reusable markdown syntax for things we need often, though.
* Code blocks with syntax highlighting, similar to Zulip's own markdown.
* Anchor tags for linking to headers in other documents.
* You can create special highlight warning blocks using e.g.:
```
!!! warn "title of warning"
    Body of warning
```

  to create a special warning block with title "title of warning" to
  highlight something important.  The whitespace is important.  Often,
  we just use "" as the title.  `!!! tip "title"` is useful for less
  scary tips.  See
  [the python-markdown docs on this extension](https://pythonhosted.org/Markdown/extensions/admonition.html)
  for details on how this extension works; essentially the value
  `warn` or `tip` is an extra CSS class added to the admonition.

#### Macros

**Macros** are elements in the format of `{!macro.md!}` that insert common phrases
and steps at the location of the macros.

##### **Administration** `{!admin.md!}` macro

* **About:** Links to the **Edit Administrator Settings** documentation. Usually
preceded by the [**Go to the** macro](#go-to-the-go-to-the-md-macro) and a link to a
particular section on the **Administration** page.

* **Contents:**
    ```.md
    tab of the [Administration](/help/edit-administrator-settings) page.
    ```

* **Example usage and rendering:**
    ```.md
    {!go-to-the.md!} [Organization Settings](/#administration/organization-settings)
    {!admin.md!}
    ```
    ```.md
    1. Go to the [OrganizationSettings](/#administration/organization-settings) tab of the
    [Administration](/help/edit-administrator-settings) page.
    ```

##### **All streams** `{!all-sreams.md!}` macro

* **About:** Explains how to view all streams in the organization on the
**Subscriptions** page. Usually formatted as a tip and preceded by the
[**Subscriptions** macro](#subscriptions-subscriptions-md-macro) and the
[**Filter streams** macro](#filter-streams-filter-streams-md-macro).

* **Contents:**
    ```.md
        If you wish to see streams that you aren't subscribed to, click on the
            **All Streams** tab; the tab will turn gray upon doing so.
    ```

* **Example usage and rendering:**

    ```.md
    {!subscriptions.md!}
    {!filter-streams.md!}
        !!! tip ""
        {!all-streams.md!}
    ```
    ```.md
    1. [Find the relevant stream](/help/browse-and-join-streams#browse-streams) on the
    [Subscriptions](/#subscriptions) page. You can search for specific streams by entering the
    name of the stream in the **Filter Streams** input.
        !!! tip ""
            If you wish to see streams that you aren't subscribed to, click on the
            **All Streams** tab; the tab will turn gray upon doing so.
    ```

##### **Down chevron** `{!down-chevron.md!}` macro

* **About:** Instructs readers to click on the down chevron (<i class="fa
fa-chevron-down"></i>) icon to reveal an actions dropdown; usually preceded by
an command, such as the [**Message actions**
macro](#message-actions-message-actions-md-macro).

* **Contents:**
    ```.md
    down chevron (<i class="icon-vector-chevron-down"></i>) icon to reveal an actions dropdown.
    ```

* **Example usage and rendering:**
    ```.md
    {!message-actions.md!}
    {!down-chevron.md!}
    ```
    ```.md
    1. Hover over a message to replace the message's timestamp with its message
    actions, represented by three icons. From the icons that appear, select the
    down chevron (<i class="icon-vector-chevron-down"></i>) icon to reveal an actions dropdown.
    ```

##### **Go to the** `{!go-to-the.md}` macro

* **About:** Usually precedes the [**Settings** macro](#settings-settings-md-macro)
or the [**Administration** macro](#administration-admin-md-macro). Transforms
following content into a step.

* **Contents:**
    ```.md
    1. Go to the
    ```

* **Example usage and rendering:**
    ```.md
    {!go-to-the.md!} [Notifications](/#settings/notifications)
    {!settings.md!}
    ```
    ```.md
    1. Go to the [Notifications](/#settings/notifications) tab on the
    [Settings](/help/edit-settings) page.
    ```

##### **Filter streams** `{!filter-streams.md!}` macro

* **About:** Explains how to search for specific streams in the
  **Subscriptions** page using the **Filter Streams** input. Usually preceded by
  the [**Subscriptions** macro](#subscriptions-subscriptions-md-macro).

* **Contents:**
    ```.md
    You can search for specific streams by entering the name of the stream in
    the **Filter Streams** input.
    ```

* **Example usage and rendering:**
    ```.md
    {!subscriptions.md!}
    {!filter-streams.md!}
    ```
    ```.md
    1. [Find the relevant stream](/help/browse-and-join-streams#browse-streams) on the
    [Subscriptions](/#subscriptions) page. You can search for specific streams by entering the
    name of the stream in the **Filter Streams** input.
    ```

##### **Message actions** `{!message-actions.md!}` macro

* **About:** Explains how to view the actions of message. Usually followed by an instruction
to click a specific icon, such as the [**Down chevron** macro](#down-chevron-down-chevron-md-macro).

* **Contents:**
    ```.md
    1. Hover over a message to replace the message's timestamp with its message
    actions, represented by three icons. From the icons that appear, select the
    ```

* **Example usage and rendering:**
    ```.md
    {!message-actions.md!}
    {!down-chevron.md!}
    ```
    ```.md
    1. Hover over a message to replace the message's timestamp with its message
    actions, represented by three icons. From the icons that appear, select the
    down chevron (<i class="icon-vector-chevron-down"></i>) icon to reveal an actions dropdown.
    ```
##### **Settings** `{!settings.md!}` macro

* **About:** Links to the **Edit Settings** documentation. Usually preceded by
the [**Go to the** macro](#go-to-the-go-to-the-md-macro) and a link to a
particular section on the **Settings** page.

* **Contents:**
    ```.md
    tab on the [Settings](/help/edit-settings) page.
    ```

* **Example usage and rendering:**
    ```.md
    {!go-to-the.md!} [Notifications](/#settings/notifications)
    {!settings.md!}
    ```
    ```.md
    1. Go to the [Notifications](/#settings/notifications) tab on the
    [Settings](/help/edit-settings) page.
    ```

##### **Stream actions** `{!stream-actions.md!}` macro

* **About:** Explains how to view the actions of stream. Usually followed by the an
instruction and the [**Down chevron** macro](#down-chevron-down-chevron-md-macro).

* **Contents:**
    ```.md
    1. On the left sidebar in the **Streams** section, hover over a stream to reveal
    a down chevron (<i class="icon-vector-chevron-down"></i>) icon to the right of
    the stream name.
    ```

* **Example usage and rendering:**
    ```.md
    {!stream-actions.md!}

    1. Click on the {!down-chevron.md!}
    ```

    ```.md
    1. On the left sidebar in the **Streams** section, hover over a stream to reveal
    a down chevron (<i class="icon-vector-chevron-down"></i>) icon to the right of
    the stream name.

    2. Click on the down chevron (<i class="icon-vector-chevron-down"></i>)
    icon to reveal an actions dropdown.
    ```

##### **Stream Settings** `{!stream-settings.md!}` macro

* **About:** Notifies readers about the changes in the
  **Subscriptions** page when a stream is selected; usually followed
  by an instruction.

* **Contents:**
    ```.md
    the right side of the [Subscriptions](/#subscriptions) page, labeled
    **Stream Settings**, will now display the selected stream's settings.
    ```

* **Example usage and rendering:**
    ```.md
    1. Click on the stream you want to edit; {!stream-settings.md!}
    ```
    ```.md
    1. Click on the stream you want to edit; the right side of the
    [Subscriptions](/#subscriptions) page, labeled **Stream Settings**, will
    now display the selected stream's settings.
    ```

##### **Stream Settings scroll** `{!stream-settings.md!}` macro

* **About:** Instructs readers to scroll down to a particular section on the
**Subscriptions** page after making sure their cursors are hovering above the
**Streams Settings** section.

* **Contents:**
    ```.md
    1. After making sure that your cursor is hovering over the **Streams Settings**
    section, scroll down to the
    ```

* **Example usage and rendering:**
    ```.md
    {!stream-settings-scroll.md!} **Stream membership** section. This section
    shows the usernames and emails of all users that are currently subscribed to the
    selected stream.
    ```
    ```.md
    1. After making sure that your cursor is hovering over the **Streams Settings**
    section, scroll down to the **Stream membership** section. This section
    shows the usernames and emails of all users that are currently subscribed to the
    selected stream.
    ```

##### **Subscriptions** `{!subscriptions.md!}` macro

* **About:** Used in documentation that direct users to the **Subscriptions** page.
Often followed by the [**Filter streams** macro](#filter-streams-filter-streams-md-macro).

* **Contents:**
    ```.md
    1. [Find the relevant stream](/help/browse-and-join-streams#browse-streams) on
    the [Subscriptions](/#subscriptions) page.
    ```

* Standard usage and rendering:
    ```.md
    {!subscriptions.md!}
    {!filter-streams.md!}
    ```
    ```.md
    1. [Find the relevant stream](/help/browse-and-join-streams#browse-streams) on the
    [Subscriptions](/#subscriptions) page. You can search for specific streams by entering the
    name of the stream in the **Filter Streams** input.
    ```

### Style guide

* Names of buttons, fields, etc. should be **bolded** (e.g. **Settings**
page, **Change Password** button, **Email** field). No quotation marks
should be used.

* All multi-step instructions should be formatted as a series of
numbered steps. E.g.:
  ```
  1. Do something
  2. Do the next thing.
  ```
  Keep the steps simple — "do X, then Y, then Z" is three steps, not one.

* Images and additional notes or instructions are kept within a single step by
indenting them.

* The first heading of a page should be prefaced with '# '. All subsequent
 subheading levels should use more '#'s
   ```
  # This is a heading

  ## This is a subheading

  ### This is a lower level subheading

  ## This is another subheading

  ### This is another lower level subheading
   ```

* Keep in mind that the UI may change — don't describe it in more detail
  than is needed.
    * Never refer specifically to button colors.

* All icons should be referenced by their names and their [FontAwesome](http://fontawesome.io)
(version 3.0.2) text icons within parentheses.
    * cog (<i class="fa fa-cog"></i>) icon — `cog (<i
    class="icon-vector-cog"></i>) icon`
    * down chevron (<i class="fa fa-chevron-down"></i>) icon —
    `down chevron (<i class="icon-vector-chevron-down"></i>) icon`
    * eye (<i class="fa fa-eye"></i>) icon — `eye (<i
    class="icon-vector-eye-open"></i>) icon`
    * file (<i class="fa fa-file-text-o"></i>) icon — `file (<i
    class="icon-vector-file-text-alt"></i>) icon`
    * filled star (<i class="fa fa-star"></i>) icon —
    `filled star (<i class="icon-vector-star"></i>) icon`
    * formatting (<i class="fa fa-font"></i>) icon —
    `formatting (<i class="icon-vector-font"></i>) icon`
    * menu (<i class="fa fa-bars"></i>) icon — `menu (<i
    class="icon-vector-reorder"></i>) icon`
    * overflow ( <i class="fa fa-ellipsis-v"></i> ) icon —
    `overflow ( <i class="icon-vector-ellipsis-verical"></i> ) icon`
    * paperclip (<i class="fa fa-paperclip"></i>) icon —
    `paperclip (<i class="icon-vector-paperclip"></i>) icon`
    * pencil (<i class="fa fa-pencil"></i>) icon —
    `pencil (<i class="icon-vector-pencil"></i>) icon`
    * pencil and paper (<i class="fa fa-pencil-square-o"></i>) icon —
    `pencil and paper (<i class="icon-vector-edit"></i>) icon`
    * plus (<i class="fa fa-plus"></i>) icon —
    `plus (<i class="icon-vector-plus"></i>) icon`
    * smiley face (<i class="fa fa-smile-o"></i>) icon —
    `smiley face (<i class="icon-vector-smile"></i>) icon`
    * star (<i class="fa fa-star-o"></i>) icon —
    `star (<i class="icon-vector-star-empty"></i>) icon`
    * trash (<i class="fa fa-trash-o"></i>) icon —
    `trash (<i class="icon-vector-trash"></i>) icon`
    * x (<i class="fa fa-times"></i>) icon —
    `x (<i class="icon-vector-remove"></i>) icon`

* Guidelines for **tips** and **warnings**:

  * A **tip** is any suggestion for the user that is not part of the main
    set of instructions. E.g. it may address a common problem users may
    encounter while following the instructions, or point to an option
    for power users.
  * A **warning** is a note on what happens when there is some kind of problem.
    Tips are more common than warnings.
  * All tips/warnings should appear inside tip/warning blocks.
    They should not be included as
    part of the numbered instructions or displayed in plain paragraphs.
  * There should be only one tip/warning inside each block. It is perfectly
    fine to use multiple consecutive tip boxes.
  * Generally, no title for the tip/warning block is needed.
  * Example **tip** from the sign-in doc page:
    ```
    !!! tip ""
        If you've forgotten your password, see the
        [Change your password](/help/change-your-password) page for
        instructions on how to reset it.
    ```
  * Other examples of **tips**:
    * Your topic name can be no longer than 52 characters.
    * If you are unsure of the code for any particular emoji visit Emoji
      Cheat Sheet for a complete list.
  * Example **warning**:
      ```
      !!! warn ""
          If you attempt to input a nonexistent stream name, an error
          message will appear.
      ```

* **Screenshot** guidelines:
  * Only include a screenshot if it will help guide the user. E.g. include a
    screenshot if the user needs to find a button in the corner. Don't
    include a screenshot if the element the user needs to interact with is
    the only thing on the page. Using too many screenshots creates problems:
      * **Maintenance**: The screen shot has to be updated every time the UI
        is changed.
      * It makes the instructions look longer and therefore more complicated.
  * Never include the whole Zulip window in a screenshot. Focus on the
    relevant part of the app.
  * The screenshot should always come *after* the text that describes it,
    never before. E.g.:

    1. Click the **Sign in with Google** button located under the **Login**
      button and **Forgot your password?** link.

      ![Zulip sign in Google](/images/signin-google.png)
