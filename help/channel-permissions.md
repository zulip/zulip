# Channel privacy settings

{!channels-intro.md!}

Zulip supports a few types of channels:

* **Public** (<i class="zulip-icon zulip-icon-hashtag"></i>):
  Members can join and view the complete message history.
  Public channels are visible to [guest users](/help/guest-users)
  only if they are subscribed (exactly like private channels with
  shared history).

* **Private** (<i class="zulip-icon zulip-icon-lock"></i>):
  New subscribers must be added by an existing subscriber. Only subscribers
  and organization administrators can see the channel's name and description,
  and only subscribers can view topics and messages with the channel:
    * In **private channels with shared history**, new subscribers can
    access the channel's full message history.
    * In **private channels with protected history**, new subscribers
    can only see messages sent after they join.

* [**Web-public**](/help/public-access-option) (<i class="zulip-icon
  zulip-icon-globe"></i>): Members can join (guests must be invited by a
  subscriber). Anyone on the Internet can view complete message history without
  creating an account.

## Privacy model for private channels

At a high level:

* Organization owners and administrators can see and modify most
  aspects of a private channel, including the membership and estimated
  traffic. Owners and administrators generally cannot see private
  channel messages or do things that would give them access to private
  channel messages, like adding new subscribers or changing the channel
  privacy settings.

* [Organization members and moderators](/help/roles-and-permissions)
  cannot easily see which private channels exist, or interact with them
  in any way until they are added.  Given a channel name, they can
  figure out whether a channel with that name exists, but cannot see
  any other details about the channel.

* From the perspective of a guest, all channels are private channels,
  and they additionally can't add other members to the channels they
  are subscribed to.

There are two situations in which an organization owner or
administrator can access private channel messages:

* Via some types of [data export](/help/export-your-organization).

* Owners and administrators can change the ownership of a bot. If a
  bot is subscribed to a private channel, then an administrator can get
  access to that channel by taking control of the bot, though the
  access will be limited to what the bot can do. (E.g. incoming
  webhook bots cannot read messages.)

## Detailed permissions

### Public channels

<div class="centered_table"></div>
|                       | Owners and admins | Moderators | Members   | Guests
|---                    |---                |            |---        |---
| View channel name     | &#10004;          | &#10004;   | &#10004;  | &#9726;
| Join                  | &#10004;          | &#10004;   | &#10004;  |
| Unsubscribe           | &#9726;           | &#9726;    | &#9726;   | &#9726;
| Add others            | &#10004;          | &#10038;   | &#10038;  |
| Remove others         | &#10004;          | &#10038;   | &#10038;  | &#10038;
| See subscriber list   | &#10004;          | &#10004;   | &#10004;  | &#9726;
| See full history      | &#10004;          | &#10004;   | &#10004;  | &#9726;
| See estimated traffic | &#10004;          | &#10004;   | &#10004;  | &#9726;
| Post                  | &#10004;          | &#10038;   | &#10038;  | &#10038;
| Change the privacy    | &#10004;          |            |           |
| Rename                | &#10004;          |            |           |
| Edit the description  | &#10004;          |            |           |
| Delete                | &#10004;          |            |           |

<span class="legend_symbol">&#10004;</span><span class="legend_label">Always</span>

<span class="legend_symbol">&#9726;</span><span class="legend_label">If subscribed to the channel</span>

<span class="legend_symbol">&#10038;</span><span class="legend_label">
Configurable. See [Channel posting policy](/help/channel-posting-policy),
[Configure who can add users][add-users], and
[Configure who can remove users][remove-users]
for details.
</span>

### Private channels

<div class="centered_table"></div>
|                       | Owners and admins | Moderators | Members   | Guests
|---                    |---                |            |---        |---
| View channel name      | &#10004;          | &#9726;    | &#9726;   | &#9726;
| Join                  |                   |            |           |
| Unsubscribe           | &#9726;           | &#9726;    | &#9726;   | &#9726;
| Add others            | &#9726;           | &#10038;   | &#10038;  |
| Remove others         | &#10004;          | &#10038;   | &#10038;  | &#10038;
| See subscriber list   | &#10004;          | &#9726;    | &#9726;   | &#9726;
| See full history      | &#10038;          | &#10038;   | &#10038;  | &#10038;
| See estimated traffic | &#10004;          | &#9726;    | &#9726;   | &#9726;
| Post                  | &#9726;           | &#10038;   | &#10038;  | &#10038;
| Change the privacy    | &#9726;           |            |           |
| Rename                | &#10004;          |            |           |
| Edit the description  | &#10004;          |            |           |
| Delete                | &#10004;          |            |           |

<span class="legend_symbol">&#10004;</span><span class="legend_label">Always</span>

<span class="legend_symbol">&#9726;</span><span class="legend_label">If subscribed to the channel</span>

<span class="legend_symbol">&#10038;</span><span class="legend_label">
Configurable, but at minimum must be subscribed to the channel.
See [Channel posting policy](/help/channel-posting-policy),
[Configure who can add users][add-users], and
[Configure who can remove users][remove-users]
for details.
</span>

## Related articles

* [Roles and permissions](/help/roles-and-permissions)
* [Channel sending policy](/help/channel-posting-policy)
* [Web-public channels](/help/public-access-option)

[add-users]: /help/configure-who-can-invite-to-channels#configure-who-can-add-users
[remove-users]: /help/configure-who-can-invite-to-channels#configure-who-can-remove-users
