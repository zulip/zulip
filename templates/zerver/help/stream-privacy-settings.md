# Stream privacy settings

There are three types of streams in Zulip.

* **Public**: Anyone can join, and anyone can view the complete message
  history without joining.

* **Private, shared history**: You must be added by a member of the stream. The
  complete message history is available as soon as you are added.

* **Private, protected history**: You must be added by a member of the
  stream. You only have access to the messages that are sent after you are added.

## Privacy model for private streams

At a high level:

* Organization admins can see and modify most aspects of a private stream,
  including the membership and estimated traffic. Admins cannot see stream
  messages or do anything that would indirectly give them access to stream
  messages, like adding members or changing the stream privacy settings.

* Non-admins cannot easily see which private streams exist, or interact with
  them in any way until they are added. Given a stream name, they can figure
  out whether a stream with that name exists, but cannot see any other
  details about the stream.

## Detailed permissions

### Public streams

|                       | Org admins | Stream members | Org members |
|---                    |---         |---             |---          |
| Join                  | &#10004;   | &mdash;        | &#10004;    |
| Add others            | &#10004;   | &#10004;       | &#10004;    |
| See subscriber list   | &#10004;   | &#10004;       | &#10004;    |
| See full history      | &#10004;   | &#10004;       | &#10004;    |
| See estimated traffic | &#10004;   | &#10004;       | &#10004;    |
| Change the privacy    | &#10004;   |                |             |
| Rename                | &#10004;   |                |             |
| Edit the description  | &#10004;   |                |             |
| Remove others         | &#10004;   |                |             |
| Delete                | &#10004;   |                |             |

### Private streams

|                       | Org admins | Stream members | Org members |
|---                    |---         |---             |---          |
| Join                  |            | &mdash;        |             |
| Add others            |            | &#10004;       |             |
| See subscriber list   | &#10004;   | &#10004;       |             |
| See full history      |            | [1]            |             |
| See estimated traffic | &#10004;   | &#10004;       |             |
| Change the privacy    | [2]        |                |             |
| Rename                | &#10004;   |                |             |
| Edit the description  | &#10004;   |                |             |
| Remove others         | &#10004;   |                |             |
| Delete                | &#10004;   |                |             |

[1] Depends on the stream type.

[2] Yes, but only if subscribed. If you have a private stream without an
admin, you'll have to add an admin in order to change the stream's privacy.
