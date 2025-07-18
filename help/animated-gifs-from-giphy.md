# Animated GIFs from GIPHY

!!! warn ""

    On self-hosted servers, this feature need to be
    [configured][configure-giphy] by a server administrator.

Zulip integrates with [GIPHY](https://giphy.com), allowing you to
conveniently search for animated GIFs and include them in your
messages.

Organization administrators can [disable previews of linked
images](/help/image-video-and-website-previews#configure-whether-image-and-video-previews-are-shown),
including GIFs. When previews are enabled, everyone can
[customize](/help/image-video-and-website-previews#configure-how-animated-images-are-played)
how animated images are played.

## Insert a GIF

{start_tabs}

{!start-composing.md!}

{tab|desktop-web}

1. Click the **add GIF** (<i class="zulip-icon zulip-icon-gif"></i>) icon at
   the bottom of the compose box.

1. Find a GIF you'd like to use.

1. Click on an image to insert it in the compose box.

!!! tip ""

    You can [preview your message](/help/preview-your-message-before-sending)
    before sending.

{end_tabs}

## Restrict maximum rating of GIFs retrieved from GIPHY

{!admin-only.md!}

By default, the GIPHY integration is configured to only retrieve GIFs
that GIPHY categorizes as rated G (General audience). You can change
this configure or disable GIPHY integration entirely:

{start_tabs}

{settings_tab|organization-settings}

1. Under **Compose settings**, select a rating for **GIPHY integration**.

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

* [Image, video and website previews](/help/image-video-and-website-previews)
* [Share and upload files](/help/share-and-upload-files)
* [Insert a link](/help/insert-a-link)
