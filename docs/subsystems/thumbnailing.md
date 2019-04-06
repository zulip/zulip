# Thumbnailing

There are two key places one would naturally want to thumbnail images
in a team chat application like Zulip:

* On the server-side, when serving inline image and URL previews in
  the bodies of messages.  This is very important for Zulip's network
  performance of low-bandwidth networks.
* In mobile apps, to avoid uploading full-size images on a mobile
  network (which Zulip does not yet implement),

Our server-side thumbnailing system is powered by [thumbor][], a
popular open source server for serving images and thumbnailing them.

Thumbor is responsible for a few things in Zulip:

* Serving all image content over HTTPS, even if the original/upstream
  image was hosted on HTTP (this was previously done by `camo` in
  older versions of Zulip; the `THUMBOR_SERVES_CAMO` setting controls
  whether Thumbor will serve the old-style Camo URLs that might be
  present in old messages).  This is important to avoid mixed-content
  warnings from browsers (which look very bad), and does have some
  real security benefit in protecting our users from malicious
  content.
* Minimizing potentially unnecessary bandwidth that might be used in
  communication between the Zulip server and clients.  Before we
  introduced this feature, uploading large photos could result in a
  bad experience for users with a slow network connection.

Thumbor handles a lot of details for us, varying from signing of
thumbnailing URLs, to caching for DoS prevention.

It is configured via the `THUMBOR_URL` and `THUMBNAIL_IMAGES` settings in
`/etc/zulip/settings.py`; you can host Thumbor on the same machine as
the Zulip server, or a remote server (which is better for isolation,
since security bugs in image-processing libraries have in the past
been a common attack vector).

The thumbnailing system is used for any images that appear in the
bodies of Zulip messages (i.e. both images linked to by users, as well
as uploaded image files.).  We exclude a few special image sources
(e.g. youtube stills) only because they are already thumbnailed.

For uploaded image files, we enforce the same security policy on
thumbnail URLs that we do for the uploaded files themselves.

A correct client implementation interacting with the thumbnailing
system should do the following:

* For serving the thumbnailed to 100px height version of images,
  nothing special is required; the client just needs to display the
  `src=` value in the `<img>` tag in the rendered message HTML.
* For displaying a "full-size" version of an image (e.g. to use in a
  lightbox), the client can access the `data-fullsize-src` attribute
  on the `<img>` tag; this will contain the URL for a full-size
  version.
* Ideally, when clicking on an image to switch from the thumbnail to
  the full-size / lightbox size, the client should immediately display
  the thumbnailed (low resolution) version and in parallel fetch the
  full-size version in the background, transparently swapping it into
  place once the full size version is available.  This provides a
  slick user experience where the user doesn't see a loading state,
  and instead just sees the image focus a few hundred milliseconds
  after clicking the image.

## URL design

The raw Thumbor URLs are ugly, and regardless, have the property that
we might want to change them over time (a classic case is if one moves
the thumbor installation to be hosted by a different server).  In
order to avoid encoding these into Zulip messages, we encode in the
[HTML rendered message content](../subsystems/markdown.html) URLs of
the form
`/thumbnail/?url=https://example.com/image.png&size=thumbnail` as the
`src` in our image tags, and that URL serves a
(configuration-dependent) redirect to the actual image hosted on
thumbor.


## Avatars, realm icons, and custom emoji

Currently, these user-uploaded content are thumbnailed by Zulip's
internal file-upload code, in part because they change rarely and
don't have the same throughput/performance requirements as
user-uploaded files.  We may later convert them to use thumbor as
well.

[thumbor]: https://github.com/thumbor/thumbor
