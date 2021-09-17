# Custom emoji

Any custom emoji an organization has uploaded are available to all users.

## Add custom emoji

{start_tabs}

{settings_tab|emoji-settings}

1. Under **Add a new emoji**, enter an **emoji name**.

1. Click **Upload image or GIF** and add a file in the PNG, JPG, or
   GIF file format. Zulip will automatically scale the image down to
   25x25 pixels.

1. Click **Add emoji**.

{end_tabs}

**Emoji names** can only contain `a-z`, `0-9`, dashes (`-`), and spaces.
Upper and lower case letters are treated the same, and underscores (`_`)
are treated the same as spaces.

### Bulk add emoji

We expose a [REST API endpoint](/api/upload-custom-emoji) for bulk uploading
emoji. Using REST API endpoints requires some technical expertise;
[contact us](/help/contact-support) if you get stuck.

## Replace a default emoji

You can replace a default emoji by adding a custom emoji of the same
name. If an emoji has several names, you must use the emoji's primary name
to replace it. You can find the primary name of an emoji by hovering over it
in the [emoji picker](/help/emoji-and-emoticons#select-from-the-emoji-picker),
while the search box is empty (you may have to scroll down a bit to find it).

## Delete custom emoji

{start_tabs}

{settings_tab|emoji-settings}

1. Click the trash icon (<i class="fa fa-trash-o"></i>) next to the
   emoji that you would like to delete.

{end_tabs}

Deleting an emoji will not affect any existing messages or emoji
reactions. Anyone can delete custom emoji they added, and organization
administrators can delete anyone's custom emoji.

## Editing permissions

By default, anyone other than guests can [add custom emoji](/help/custom-emoji) to the
organization. However, you can restrict the permission to add custom emoji to other sets of
roles:

* Organization administrators
* Organization administrators and moderators
* Organization administrators and all members
* Organization administrators and [full members](/help/restrict-permissions-of-new-members)

### Change who can add custom emoji

{!admin-only.md!}

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Other permissions**, configure **Who can add custom emoji**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Emoji and emoticons](/help/emoji-and-emoticons)
* [Emoji reactions](/help/emoji-reactions)
