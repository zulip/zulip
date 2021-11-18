# Web public streams

!!! warn ""

    This feature is under development, and is not yet available on Zulip Cloud.

Administrators may enable the option to create **web public streams**.
Web public streams can be viewed by anyone on the internet without logging
into your organization.

For example, you can link to a Zulip topic in a web public stream from a GitHub issue,
a social media post or a forum thread, and anyone will be able to view the
discussion without logging in. Users will still be required to log in if they
wish to post content.

## Enabling web public streams in your organization

Enabling web public streams makes it possible to create web public streams in
your organization. It also makes certain information about your organization
accessible via the Zulip API.

Web public streams are disabled by default for all organizations.

### Information that can be accessed via API when web public streams are enabled
The following information about your organization can be accessed via the Zulip
API if web public streams are enabled, whether or not any such streams have been
created.

* Organization settings, including...
* Names of users.
* Names of user groups and their membership.

Enabling web public streams is thus primarily recommended for open communities such as
open-source projects and research communities.

### How to enable or disable web public streams

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Stream permissions**, toggle the checkbox labeled "Allow creating web-public streams
   (visible to anyone on the Internet)".

{end_tabs}

### How to set permissions for creating web public streams

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Stream permissions**, make sure the checkbox labeled "Allow creating web-public streams
   (visible to anyone on the Internet)" is checked.

3. Under **Who can create web public streams?**, select the option you prefer.

{end_tabs}

## Creating a web public stream

To create a new web public stream, follow the
[instructions for creating stream](/help/create-a-stream#create-a-stream_1), selecting the **Web public** option
for **Who can access the stream?**.

To make an existing stream web public, follow the instructions to [change the privacy of a
stream](/help/change-the-privacy-of-a-stream), selecting the **Web public** option
for **Who can access the stream?**.

## What can logged out users see?

Logged out users see the web-public streams in your organization, and the
topics, messages (including uploaded files) and emoji reactions in those
streams.

A variety of information about your organization and other users is hidden from
logged out users, or only available through the API.

### Information about the organization

* Logged out users cannot view organization statistics.
* Organization settings and stream menus are hidden from the user interface for
  logged out users. Note that the information in these menus [may be accessed via
  API][info-via-api].

[info-via-api]: /help/web-public-streams#information-that-can-be-accessed-via-api-when-web-public-streams-are-enabled

### Information about users

Logged out users can see the following info about users who participate in web
public streams. They do not see this information about users who do not participate in web
public streams in the Zulip UI, though they may access it via the Zulip API.

* Name
* Avatar
* Role (e.g. Administrator)
* Join date

The following information requires login to access:

* Presence information, i.e. whether the user is currently online, their status,
  and whether they have set themselves as unavailable.

The following information is hidden from the UI for logged out users, but
may be accessed via API:

* What streams a user is subscribed to.
* What groups a user belongs to.

## What can logged out users do?

Logged out users can browse content in web public streams. They **cannot**:

* Send messages.
* React with emoji.
* Participate in polls, or otherwise interact with any message content.

## Related articles

* [Moderating open organizations](/help/moderating-open-organizations)
* [Stream permissions](/help/stream-permissions)
* [Restrict stream creation](/help/configure-who-can-create-streams)
