# Custom emoji

Custom emoji can be used by all users in an organization (including
bots).  They are supported everywhere that Zulip supports emoji,
including [emoji reactions][emoji-reactions],
[messages][emoji-messages], [channel descriptions][emoji-channels] and
[user statuses][emoji-status].

[emoji-reactions]: /help/emoji-reactions
[emoji-messages]: /help/format-your-message-using-markdown#emoji-and-emoticons
[emoji-channels]: /help/change-the-channel-description
[emoji-status]: /help/status-and-availability

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
in the [emoji picker](/help/emoji-and-emoticons#use-an-emoji-in-your-message),
while the search box is empty (you may have to scroll down a bit to find it).

## Deactivate custom emoji

{start_tabs}

{settings_tab|emoji-settings}

1. Click the **trash** (<i class="fa fa-trash-o"></i>) icon next to the
   emoji that you would like to deactivate.

{end_tabs}

Deactivating an emoji will not affect any existing messages or emoji
reactions. Anyone can deactivate custom emoji they added, and organization
administrators can deactivate anyone's custom emoji.

## Change who can add custom emoji

{!admin-only.md!}

By default, anyone other than guests can [add custom emoji](/help/custom-emoji)
to the organization. However, you can restrict the ability to do so to specific
[roles](/help/roles-and-permissions).

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Other permissions**, configure **Who can add custom emoji**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Emoji and emoticons](/help/emoji-and-emoticons)
* [Emoji reactions](/help/emoji-reactions)
