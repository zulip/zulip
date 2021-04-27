# Animated GIFs from GIPHY

Zulip integrates with [GIPHY](https://giphy.com), allowing you to
conveniently search for animated GIFs and include them in your
messages.

Be thoughtful when using this feature! Animated GIFs can be fun, but
they can also distract from the content of a conversation.

1. First, [open the compose box](/help/open-the-compose-box).
1. **Click the GIPHY logo** at the bottom of the compose box. This
   opens the GIPHY search tool.
1. Use the search tool to find a GIF you'd like to use.
1. **Click on an image** to insert a link to the GIF in the compose box.
1. Send the message.  Zulip will display the GIF like any other linked
   image.

You can [preview the
message](/help/preview-your-message-before-sending) before sending to
see what the message will look like.

## Restrict maximum rating of GIFs retrieved from GIPHY

{!admin-only.md!}

By default, the GIPHY integration is configured to only retrieve GIFs
that GIPHY categorizes as rated G (General audience). You can change
this configure or disable GIPHY integration entirely:

{start_tabs}

{settings_tab|organization-settings}

1. Under **Other settings**, select a rating from **Maximum rating of GIFs**.

{!save-changes.md!}

{end_tabs}

## Troubleshooting

* If you don't see the GIPHY icon, this is likely because you are
  using a self-hosted Zulip server that has not [configured the GIPHY
  integration][configure-giphy].

[configure-giphy]: https://zulip.readthedocs.io/en/latest/production/giphy-gif-integration.html

* If your GIFs only appear as links after sending them, this is likely
because the organization has disabled [previews of linked
images](/help/allow-image-link-previews).
