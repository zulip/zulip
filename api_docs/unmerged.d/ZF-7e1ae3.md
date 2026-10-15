* [Message formatting](/api/message-formatting#images): Markdown image
  syntax for an uploaded file that the server can't preview as an
  image or audio player now renders as a link to the file (plus a
  video preview, for a video), rather than as literal Markdown text.
  If thumbnailing an image in Markdown image syntax fails after the
  message is sent, the image is now replaced with that link, rather
  than removed.
