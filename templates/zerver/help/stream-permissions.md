# Stream privacy settings

Streams are similar to chatrooms, IRC channels, or email lists in that they
determine who receives a message. There are three types of streams in Zulip.

* **Public**: Anyone other than guests can join, and anyone (other than guests) can view the complete message
  history without joining.

* **Private, shared history**: You must be added by a member of the stream. The
  complete message history is available as soon as you are added.

* **Private, protected history**: You must be added by a member of the
  stream. You only have access to the messages that are sent after you are added.

## Privacy model for private streams

At a high level:

* Organization admins can see and modify most aspects of a private stream,
  including the membership and estimated traffic. Admins generally cannot see stream
  messages or do things that would indirectly give them access to stream
  messages, like adding members or changing the stream privacy settings.

* Non-admin members cannot easily see which private streams exist, or interact with
  them in any way until they are added. Given a stream name, they can figure
  out whether a stream with that name exists, but cannot see any other
  details about the stream.

* From the perspective of a guest, all streams are private streams, and they
  additionally can't add other members to the streams they are subscribed to.

There are two situations in which an organization administrator can access
private stream messages:

* Via some types of [data export](/help/export-your-organization).

* Administrators can change the ownership of a bot. If a bot is subscribed
  to a private stream, then an administrator can get access to that stream by
  taking control of the bot, though the access will be limited to what the
  bot can do. (E.g. incoming webhook bots cannot read messages.)

## Detailed permissions

### Public streams

|                       | Org admins | Stream members | Org members | Guests
|---                    |---         |---             |---          |---
| Join                  | &#10004;   | &mdash;        | &#10004;    |
| Add others            | &#10004;   | [1]            | &#10004;    |
| See subscriber list   | &#10004;   | &#10004;       | &#10004;    |
| See full history      | &#10004;   | &#10004;       | &#10004;    |
| See estimated traffic | &#10004;   | &#10004;       | &#10004;    |
| Post                  | &#10004;   | [2]            |             |
| Change the privacy    | &#10004;   |                |             |
| Rename                | &#10004;   |                |             |
| Edit the description  | &#10004;   |                |             |
| Remove others         | &#10004;   |                |             |
| Delete                | &#10004;   |                |             |

[1] Yes, except for guests.

[2] Configurable.

### Private streams

|                       | Org admins | Stream members | Org members | Guests
|---                    |---         |---             |---          |---
| Join                  |            | &mdash;        |             |
| Add others            |            | [1]            |             |
| See subscriber list   | &#10004;   | &#10004;       |             |
| See full history      |            | [3]            |             |
| See estimated traffic | &#10004;   | &#10004;       |             |
| Post                  | &#10004;   | [2]            |             |
| Change the privacy    | [4]        |                |             |
| Rename                | &#10004;   |                |             |
| Edit the description  | &#10004;   |                |             |
| Remove others         | &#10004;   |                |             |
| Delete                | &#10004;   |                |             |

[1] Yes, except for guests.

[2] Configurable.

[3] Depends on the stream type.

[4] Yes, but only if subscribed. If you have a private stream without an
admin, you'll have to add an admin in order to change the stream's privacy.
