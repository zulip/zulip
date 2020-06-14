# Stream privacy settings

Streams are similar to chatrooms, IRC channels, or email lists in that they
determine who receives a message. There are three types of streams in Zulip.

* **Public**: Anyone other than guests can join, and anyone (other
  than guests) can view the complete message history without joining.

* **Private, shared history**: You must be added by a member of the stream. The
  complete message history is available as soon as you are added.

* **Private, protected history**: You must be added by a member of the
  stream. You only have access to the messages that are sent after you are added.

## Privacy model for private streams

At a high level:

* Organization owners and administrators can see and modify most
  aspects of a private stream, including the membership and estimated
  traffic. Owners and administrators generally cannot see private
  stream messages or do things that would give them access to private
  stream messages, like adding new subscribers or changing the stream
  privacy settings.

* [Organization members](/help/roles-and-permissions) cannot easily
  see which private streams exist, or interact with them in any way
  until they are added.  Given a stream name, they can figure out
  whether a stream with that name exists, but cannot see any other
  details about the stream.

* From the perspective of a guest, all streams are private streams, and they
  additionally can't add other members to the streams they are subscribed to.

There are two situations in which an organization owner or
administrator can access private stream messages:

* Via some types of [data export](/help/export-your-organization).

* Owners and administrators can change the ownership of a bot. If a
  bot is subscribed to a private stream, then an administrator can get
  access to that stream by taking control of the bot, though the
  access will be limited to what the bot can do. (E.g. incoming
  webhook bots cannot read messages.)

## Detailed permissions

### Public streams

|                       | Owners and admins | Members   | Guests
|---                    |---                |---        |---
| Join                  | &#10004;          | &#10004;  |
| Unsubscribe           | &#9726;           | &#9726;   | &#9726;
| Add others            | &#10004;          | &#10004;  |
| See subscriber list   | &#10004;          | &#10004;  | &#9726;
| See full history      | &#10004;          | &#10004;  | &#9726;
| See estimated traffic | &#10004;          | &#10004;  | &#9726;
| Post                  | &#10004;          | &#10038;  | &#10038;
| Change the privacy    | &#10004;          |           |
| Rename                | &#10004;          |           |
| Edit the description  | &#10004;          |           |
| Remove others         | &#10004;          |           |
| Delete                | &#10004;          |           |

&#10004; Always

&#9726; &nbsp; If subscribed to the stream

&#10038; [Configurable](/help/stream-sending-policy).  Owners,
Administrators, and Members can, by default, post to any public
stream, and Guests can only post to public streams if they are
subscribed.

### Private streams


|                       | Owners and admins | Members   | Guests
|---                    |---                |---        |---
| Join                  |                   |           |
| Unsubscribe           | &#9726;           | &#9726;   | &#9726;
| Add others            | &#9726;           | &#9726;   |
| See subscriber list   | &#10004;          | &#9726;   | &#9726;
| See full history      | &#10038;          | &#10038;  | &#10038;
| See estimated traffic | &#10004;          | &#9726;   | &#9726;
| Post                  | &#9726;           | &#10038;  | &#10038;
| Change the privacy    | &#9726;           |           |
| Rename                | &#10004;          |           |
| Edit the description  | &#10004;          |           |
| Remove others         | &#10004;          |           |
| Delete                | &#10004;          |           |

&#10004; Always

&#9726; &nbsp; If subscribed to the stream

&#10038; [Configurable](/help/stream-sending-policy), but at minimum
must be subscribed to the stream.

## Related articles

* [Roles and permissions](/help/roles-and-permissions)
* [Stream sending policy](/help/stream-sending-policy)
