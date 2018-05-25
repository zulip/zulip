# Stream permissions

In zulip, a user's ability to interact with a stream is dependent on the type
of stream, and the role a user has with an organization, and the relationship
a user has with a stream.

## Types of streams

**Public** are generally available to members of a zulip
organization.

**Private** are available to people who have been specifically
invited to that stream.

**Private with History** are like private streams, but someone
who joins the stream can see history from before they joined.

## Organization Roles

**Organization Administrators** control the organization settings, members, and
streams.

**Members** have access to all public streams in the organization.

**Guests** have access to streams to which they have been invited.

## Stream Relationships

**Subscribers** can view and post messages in a stream.

**Non-subscribers** cannot view messages in a stream.

## Public Streams
### Key

&#10004; - always

&#9652; - if subscribed

<table class="permissions-table">
    <thead>
  <tr>
    <th>&nbsp;</th>
    <th>Org Admins </th>
    <th>Members</th>
    <th>Guests</th>
  </tr>
</thead>
<tbody>
   <tr>
    <td>See the stream listing</td>
    <td><!-- Org Admins --> &#10004;</td>
    <td><!-- Members of the org  -->&#10004; </td>
    <td><!-- Guests -->&#10004; </td>
  </tr>
  <tr>
    <td>Subscribe</td>
    <td><!-- Org Admins --> &#10004;</td>
    <td><!-- Members of the org  -->&#10004; </td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Read New Messages</td>
    <td><!-- Org Admins --> &#9652;</td>
    <td><!-- Members of the org  -->&#9652; </td>
    <td><!-- Guests -->&#9652;</td>
  </tr>
  <tr>
    <td>Read Messages from Before Joining</td>
    <td><!-- Org Admins --> &#9652;</td>
    <td><!-- Members of the org  -->&#9652; </td>
    <td><!-- Guests -->&#9652;</td>
  </tr>
  <tr>
    <td>Post Messages</td>
    <td><!-- Org Admins --> &#9652;*</td>
    <td><!-- Members of the org  -->&#9652;*</td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Create new topics</td>
    <td><!-- Org Admins --> &#9652;*</td>
    <td><!-- Members of the org  -->&#9652;*</td>
    <td><!-- Guests -->&#9652;</td>
  </tr>
  <tr>
    <td>See who is subscribed</td>
    <td><!-- Org Admins -->&#10004;</td>
    <td><!-- Members of the org  -->&#10004;</td>
    <td><!-- Guests -->&#10004;</td>
  </tr>
  <tr>
    <td>Add others</td>
    <td><!-- Org Admins -->&#9652;</td>
    <td><!-- Members of the org  -->&#9652;</td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Unsubscribe others</td>
    <td><!-- Org Admins -->&#10004;</td>
    <td><!-- Members of the org  -->&nbsp;</td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Edit name and description</td>
    <td><!-- Org Admins -->&#10004;</td>
    <td><!-- Members of the org  -->&nbsp;</td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Delete stream</td>
    <td><!-- Org Admins -->&#10004;</td>
    <td><!-- Members of the org  -->&nbsp;</td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Change privacy</td>
    <td><!-- Org Admins -->&#10004;</td>
    <td><!-- Members of the org  -->&nbsp;</td>
    <td><!-- Guests --></td>
  </tr>
  <tr>
    <td>See average messages per week</td>
    <td><!-- Org Admins -->&#10004;</td>
    <td><!-- Members of the org  -->&#10004;</td>
    <td><!-- Guests -->&#10004;</td>
  </tr>
</tbody></table>

\* Posting to a stream without being subscribed to a public stream will cause a
user to become subscribed.

## Private Streams
### Key

&#10004; - always

&#9652; - if subscribed

<table class="permissions-table">
    <thead>
  <tr>
    <th>&nbsp;</th>
    <th>Org Admins </th>
    <th>Members</th>
    <th>Guests</th>
  </tr>
</thead>
<tbody>
   <tr>
    <td>See the stream listing</td>
    <td><!-- Org Admins --> &#10004;</td>
    <td><!-- Members of the org  --> </td>
    <td><!-- Guests --> </td>
  </tr>
  <tr>
    <td>Subscribe</td>
    <td><!-- Org Admins --> </td>
    <td><!-- Members of the org  --></td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Read New Messages</td>
    <td><!-- Org Admins --> &#9652;</td>
    <td><!-- Members of the org  -->&#9652; </td>
    <td><!-- Guests -->&#9652;</td>
  </tr>
  <tr>
    <td>Read Messages from Before Joining</td>
    <td><!-- Org Admins --> &#9652;*</td>
    <td><!-- Members of the org  -->&#9652;*</td>
    <td><!-- Guests -->&#9652;*</td>
  </tr>
  <tr>
    <td>Post Messages</td>
    <td><!-- Org Admins --> &#9652;</td>
    <td><!-- Members of the org  -->&#9652;</td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Create new topics</td>
    <td><!-- Org Admins --> &#9652;</td>
    <td><!-- Members of the org  -->&#9652;</td>
    <td><!-- Guests -->&#9652;</td>
  </tr>
  <tr>
    <td>See who is subscribed</td>
    <td><!-- Org Admins -->&#10004;</td>
    <td><!-- Members of the org  --></td>
    <td><!-- Guests --></td>
  </tr>
  <tr>
    <td>Add others</td>
    <td><!-- Org Admins -->&#9652;</td>
    <td><!-- Members of the org  -->&#9652;</td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Unsubscribe others</td>
    <td><!-- Org Admins -->&#10004;</td>
    <td><!-- Members of the org  -->&nbsp;</td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Edit name and description</td>
    <td><!-- Org Admins -->&#10004;</td>
    <td><!-- Members of the org  -->&nbsp;</td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Delete stream</td>
    <td><!-- Org Admins -->&#10004;</td>
    <td><!-- Members of the org  -->&nbsp;</td>
    <td><!-- Guests -->&nbsp;</td>
  </tr>
  <tr>
    <td>Change privacy</td>
    <td><!-- Org Admins -->&#9652;</td>
    <td><!-- Members of the org  -->&nbsp;</td>
    <td><!-- Guests --></td>
  </tr>
  <tr>
    <td>See average messages per week</td>
    <td><!-- Org Admins -->&#10004;</td>
    <td><!-- Members of the org  --></td>
    <td><!-- Guests --></td>
  </tr>
</tbody></table>

\* Only subscribers of "Private with History" streams can see message history
from before they joined.
