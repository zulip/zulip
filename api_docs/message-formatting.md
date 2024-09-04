# Message formatting

Zulip supports an extended version of Markdown for messages, as well as
some HTML level special behavior. The Zulip help center article on [message
formatting](/help/format-your-message-using-markdown) is the primary
documentation for Zulip's markup features. This article is currently a
changelog for updates to these features.

The [render a message](/api/render-message) endpoint can be used to get
the current HTML version of any Markdown syntax for message content.

## Code blocks

**Changes**: As of Zulip 4.0 (feature level 33), [code blocks][help-code]
can have a `data-code-language` attribute attached to the outer HTML
`div` element, which records the programming language that was selected
for syntax highlighting. This field is used in the
[playgrounds][help-playgrounds] feature for code blocks.

## Global times

**Changes**: In Zulip 3.0 (feature level 8), added [global time
mentions][help-global-time] to supported Markdown message formatting
features.

## Image previews

When a Zulip message is sent linking to an uploaded image, Zulip will
generate an image preview element with the following format.

``` html
<div class="message_inline_image">
    <a href="/user_uploads/path/to/image.png" title="image.png">
        <img data-original-dimensions="1920x1080"
          src="/user_uploads/thumbnail/path/to/image.png/840x560.webp">
    </a>
</div>
```

If the server has not yet generated thumbnails for the image yet at
the time the message is sent, the `img` element will be a temporary
loading indicator image and have the `image-loading-placeholder`
class, which clients can use to identify loading indicators and
replace them with a more native loading indicator element if
desired. For example:

``` html
<div class="message_inline_image">
    <a href="/user_uploads/path/to/image.png" title="image.png">
        <img class="image-loading-placeholder" data-original-dimensions="1920x1080" src="/path/to/spinner.png">
    </a>
</div>
```

Once the server has a working thumbnail, such messages will be updated
via an `update_message` event, with the `rendering_only: true` flag
(telling clients not to adjust message edit history), with appropriate
adjusted `rendered_content`. A client should process those events by
just using the updated rendering. If thumbnailing failed, the same
type of event will edit the message's rendered form to remove the
image preview element, so no special client-side logic should be
required to process such errors.

Note that in the uncommon situation that the thumbnailing system is
backlogged, an individual message containing multiple image previews
may be re-rendered multiple times as each image finishes thumbnailing
and triggers a message update.

Clients are recommended to do the following when processing image
previews:

- Clients that would like to use the image's aspect ratio to lay out
  one or more images in the message feed may use the
  `data-original-dimensions` attribute, which is present even if the
  image is a placeholder spinner.  This attribute encodes the
  dimensions of the original image as `{width}x{height}`.  These
  dimensions are for the image as rendered, _after_ any EXIF rotation
  and mirroring has been applied.
- If the client would like to control the thumbnail resolution used,
  it can replace the final section of the URL (`840x560.webp` in the
  example above) with the `name` of its preferred format from the set
  of supported formats provided by the server in the
  `server_thumbnail_formats` portion of the `register`
  response. Clients should not make any assumptions about what format
  the server will use as the "default" thumbnail resolution, as it may
  change over time.
- Download button type elements should provide the original image
  (encoded via the `href` of the containing `a` tag).
- Lightbox elements for viewing an image should be designed to
  immediately display any already-downloaded thumbnail while fetching
  the original-quality image or an appropriate higher-quality
  thumbnail from the server, to be transparently swapped in once it is
  available. Clients that would like to size the lightbox based on the
  size of the original image can use the `data-original-dimensions`
  attribute, as described above.
- Animated images will have a `data-animated` attribute on the `img`
  tag. As detailed in `server_thumbnail_formats`, both animated and
  still images are available for clients to use, depending on their
  preference. See, for example, the [web setting][help-previews]
  to control whether animated images are autoplayed in the message
  feed.
- Clients should not assume that the requested format is the format
  that they will receive; in rare cases where the client has an
  out-of-date list of `server_thumbnail_formats`, the server will
  provide an approximation of the client's requested format.  Because
  of this, clients should not assume that the pixel dimensions or file
  format match what they requested.
- No other processing of the URLs is recommended.

**Changes**: In Zulip 9.2 (feature levels 278-279, and 287+), added
`data-original-dimensions` to the `image-loading-placeholder` spinner
images, containing the dimensions of the original image.

In Zulip 9.0 (feature level 276), added `data-original-dimensions`
attribute to images that have been thumbnailed, containing the
dimensions of the full-size version of the image. Thumbnailing itself
was reintroduced at feature level 275.

Previously, with the exception of Zulip servers that used the beta
Thumbor-based implementation years ago, all image previews in Zulip
messages were not thumbnailed; the `a` tag and the `img` tag would both
point to the original image.

Clients that correctly implement the current API should handle
Thumbor-based older thumbnails correctly, as long as they do not
assume that `data-original-dimension` is present. Clients should not
assume that messages sent prior to the introduction of thumbnailing
have been re-rendered to use the new format or have thumbnails
available.

## Mentions

**Changes**: In Zulip 9.0 (feature level 247), `channel` was added
to the supported [wildcard][help-mention-all] options used in the
[mentions][help-mentions] Markdown message formatting feature.

## Spoilers

**Changes**: In Zulip 3.0 (feature level 15), added
[spoilers][help-spoilers] to supported Markdown message formatting
features.

## Removed features

**Changes**: In Zulip 4.0 (feature level 24), the rarely used `!avatar()`
and `!gravatar()` markup syntax, which was never documented and had an
inconsistent syntax, were removed.

## Related articles

* [Markdown formatting](/help/format-your-message-using-markdown)
* [Send a message](/api/send-message)
* [Render a message](/api/render-message)

[help-code]: /help/code-blocks
[help-playgrounds]: /help/code-blocks#code-playgrounds
[help-spoilers]: /help/spoilers
[help-global-time]: /help/global-times
[help-mentions]: /help/mention-a-user-or-group
[help-mention-all]: /help/mention-a-user-or-group#mention-everyone-on-a-channel
[help-previews]: /help/image-video-and-website-previews#configure-how-animated-images-are-played
