# Thumbnailing

## libvips

Zulip uses the [`libvips`](https://www.libvips.org/) image processing toolkit
for thumbnailing, as a low-memory and high-performance image processing
library. Some smaller images are thumbnailed synchronously inside the Django
process, but the majority of the work is offloaded to one or more `thumbnail`
worker processes.

Thumbnailing is a notoriously high-risk surface from a security standpoint,
since it parses arbitrary binary user input with often complex grammars. On
versions of `libvips` which support it (>= 8.13, on or after Ubuntu 24.04 or
Debian 12), Zulip limits `libvips` to only the image parsers and libraries whose
image formats we expect to parse, all of which are fuzz-tested by
[`oss-fuzz`](https://google.github.io/oss-fuzz/).

## Avatars

Avatar images are served at two of potential resolutions (100x100 and 500x500,
the latter of which is called "medium"), and always as PNGs. These are served
from a "dumb" endpoint -- that is, if S3 is used, we provide a direct link to
the content in the S3 bucket (or a Cloudfront distribution in front of it), and
the request does not pass through the Zulip server. This is because avatars are
referenced in emails, and thus their URLs need to be permanent and
publicly-accessible. This also means that any choice of resolution and file
format needs to be entirely done by the client.

Avatars are thumbnailed synchronously upon upload into 100x100 and 500x500 PNGs;
the originals are not preserved. The smallest dimension is scaled to fit, and
the largest dimension is cropped centered; the image may be scaled _up_ to fit
the 100x100 or 500x500 dimensions. To generate the filename, the server hashes
the avatar salt (a server-side secret), the user-id, and a per-user sequence
(the "version") to produce a filename which is not enumerable, and can only be
determined by the server. Hashing the version means that avatars can be served
with long-lasting caching headers.

The original avatar image is stored adjacent to the thumbnailed versions,
enabling later re-thumbnailing to other dimensions or formats without requiring
users to re-upload it.

## Emoji

Emoji URLs are hard-coded into emails, and as such their URLs need to be
permanent and publicly-accessible. They are served at a consistent 1:1 aspect
ratio, and while they may be rendered at different scales based on the
line-height of the client, we only need to store them at one resolution.

Emoji are thumbnailed synchronously into 64x64 images, and they are saved in
the same file format that they were uploaded in. Transparent pixels are added
to the smaller dimension to make the image square after resizing. The filename
of the emoji is based on a hash of the avatar salt (a server-side secret) and
the emoji's id -- but because the filename is stored in the database, it can be
anything with sufficient entropy to not be enumerable or have collisions.

For animated emoji, a separate "still" version of the emoji is generated from
the first frame, as a 64x64 PNG image. This is currently mostly unused, but is
intended to be part of a user preference to disable emoji animations (see
[#13434](https://github.com/zulip/zulip/issues/13434)). Current use is limited
to [user status](https://zulip.com/help/status-and-availability) display in
the the buddy list. When a user uses an animated emoji as their status, the
"still" version is used.

The original emoji is stored adjacent to the thumbnailed version, enabling later
re-thumbnailing to other dimensions or formats without requiring users to
re-upload it.

There is no technical reason that we preserve the uploader's choice of file
format, or that we use PNGs as the file format for the "still" version. Both of
these would plausibly benefit from being WebP images.

## Realm logos

Realm logos are converted to PNGs, thumbnailed down to fit within 800x100; a
1000x10 pixel image will end up as 800x8, and a 10x20 will end up 10x20. The
original is stored adjacent to the converted thumbnail.

## Realm icons

Realm icons are converted to PNGs, and treated identical to avatars, albeit only
producing the 100x100 size.

## File uploads

### Images

When an image file (as determined by the browser-supplied content-type) is
uploaded, we immediately upload the original content into S3 or onto disk. Its
headers are then examined, and used to create an ImageAttachment row, with
properties determined from the image; `thumbnail_metadata` is left empty. A
task is dispatched to the `thumbnail` worker to generate thumbnails in all of
the format/size combinations that the server currently has configured.

Because we parse the image headers enough to extract size information at upload
time, this also serves as a check that the upload is indeed a valid image. If
the image is determined to be invalid at this stage, the file upload returns
200, but the message content is left with a link to the uploaded content, not an
inline image.

When a message is sent, it checks the ImageAttachment rows for each referenced
image; if they have a non-empty `thumbnail_metadata`, then it writes out an
`img` tag pointing to one of them (see below); otherwise, it writes out a
specially-tagged "spinner" image, which indicates the server is still processing
the upload. The image tag encodes the original dimensions and if the image is
animated into the rendered content so clients can reserve the appropriate space
in the viewport.

If a message is rendered with a spinner, it also inserts the image into the
`thumbnail` worker's queue. This is generally redundant -- the image was
inserted into the queue when the image was uploaded. The exception is if the
image was uploaded prior to the existence of thumbnailing support, in which case
the additional queue insertion is required to have the spinner ever resolve.
Since the worker takes no action if all necessary thumbnails already exist,
this has little cost in general.

The `thumbnail` worker generates the thumbnails, uploads them to S3 or disk, and
then updates the `thumbnail_metadata` of the ImageAttachment row to contain a
list of formats/sizes which thumbnails were generated in. At the time of commit,
if there are already messages which reference the attachment row, then we do a
"silent" update of all of them to remove the "spinner" and insert an image.

In either case, the image which is inserted into the message body is at a
"reasonable" scale and format, as decided by the server. The paths to all the
generated thumbnails are not specified in the message content -- instead, the
client is told at registration time the set of formats/sizes which the server
supports, and knows how to transform any single thumbnailed path into any of the
other supported thumbnail variants. The client is responsible for choosing the
most appropriate format/size based on viewport size and format support, and
rewriting the URL accordingly.

All requests for images go through `/user_uploads`, which is processed by
Django. Any request for an ImageAttachment URL is first determined to be a valid
format/size for the server's current configuration; if is not valid, the server
may return any other thumbnail of its choosing (preferring similar sizes, and
accepted formats based on the client's `Accepts` header).

If the request is for a thumbnail format/size which is supported by the server,
but not in the ImageAttachment's `thumbnail_metadata` (as would happen if the
server's supported set is added to over time) then the server should generate,
store, and return the requested format/size on-demand.

### Migrations

Historical image uploads have ImageAttachment rows generated for them, but not
thumbnails. If the message content is re-rendered (for instance, due to being
edited) then it will trigger the image to be thumbnailed.

### Videos and PDFs

The thumbnailing system only processes images; it does not transcode videos or produce
image renderings of documents (e.g., PDFs), though those are natural potential
extensions.
