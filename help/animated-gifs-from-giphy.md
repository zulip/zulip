# Animated GIFs from GIPHY

!!! tip ""

    This feature is not available on self-hosted Zulip servers where
    the [GIPHY integration][configure-giphy] has not been configured
    by a system administrator.

Zulip integrates with [GIPHY](https://giphy.com), allowing you to
conveniently search for animated GIFs and include them in your
messages.

Be thoughtful when using this feature! Animated GIFs can be fun, but
they can also distract from the content of a conversation.

{start_tabs}
1. First, [open the compose box](/help/open-the-compose-box).

1. **Click the GIPHY logo** at the bottom of the compose box. This
   opens the GIPHY search tool.

1. Use the search tool to find a GIF you'd like to use.

1. **Click on an image** to insert a link to the GIF in the compose box.

1. Send the message.  Zulip will display the GIF like any other linked
   image.
{end_tabs}

You can [preview the
message](/help/preview-your-message-before-sending) before sending to
see what the message will look like.

Note that some organizations disable [previews of linked
images](/help/allow-image-link-previews).

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

## Privacy

GIPHY is a third-party service owned by Facebook, and any text you
enter into Zulip's GIPHY search box will be sent by your browser to
GIPHY's servers via the GIPHY API. Because this request is done
directly by your browser, GIPHY will be able to see your IP address,
and may use that data to track you, similar to if you visited the
GIPHY website and typed the same search keywords there.

Zulip proxies all external images in messages through the server,
including those from GIPHY, to prevent images from being used to track
recipients of GIFs from GIPHY.

[configure-giphy]: https://zulip.readthedocs.io/en/stable/production/giphy-gif-integration.html

## Related articles

* [Share and upload files](/help/share-and-upload-files)
* [Insert a link](/help/insert-a-link)
