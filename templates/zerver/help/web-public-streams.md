# Web-public streams

!!! warn ""

    This feature is under development, and is not yet available on Zulip Cloud.

Administrators may enable the option to create **web-public streams**.
Web-public streams can be viewed by anyone on the Internet without
creating an account in your organization.

For example, you can [link to a Zulip
topic](/help/link-to-a-message-or-conversation) in a web-public stream
from a GitHub issue, a social media post, or a forum thread, and
anyone will be able to click the link and view the discussion in the
Zulip web application without needing to create an account.

Users who wish to post content will need to create an account in order
to do so.

Web-public streams are indicated with a globe (<i class="fa
fa-globe"></i>) icon.

## Enabling web-public streams in your organization

Enabling web-public streams makes it possible to create web-public
streams in your organization. It also makes certain information about
your organization accessible to anyone on the Internet via the Zulip
API (details below).

To help protect closed organizations, creating web-public streams is
disabled by default for all organizations.

### Information that can be accessed via API when web-public streams are enabled

The following information about your organization can be accessed via the Zulip
API if web-public streams are enabled and there is currently at least one
web-public stream.

* The organization's settings (linkifiers, custom emoji, permissions
  settings, etc.)
* Names of users
* Names of user groups and their membership
* Names and descriptions of streams

Enabling web-public streams is thus primarily recommended for open
communities such as open-source projects and research communities.

### Enable or disable web-public streams

!!! warn ""
    Self-hosted Zulip servers must enable support for web-public streams by setting
    `WEB_PUBLIC_STREAMS_ENABLED = True` in their [server
    settings](https://zulip.readthedocs.io/en/latest/production/settings.html)
    prior to proceeding.

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Stream permissions**, toggle the checkbox labeled "Allow
   creating web-public streams (visible to anyone on the Internet)".

{end_tabs}

### Manage who can create web-public streams

{start_tabs}

{settings_tab|organization-permissions}

2. Under **Stream permissions**, make sure the checkbox labeled "Allow
   creating web-public streams (visible to anyone on the Internet)" is
   checked.

3. Under **Who can create web-public streams?**, select the option you prefer.

{end_tabs}

!!! tip ""
    See [Managing abuse](#managing-abuse) to learn why only
    trusted roles like Moderators and Administrators can create web-public streams.

## Creating a web-public stream

To create a new web-public stream, follow the [instructions for
creating stream](/help/create-a-stream#create-a-stream_1), selecting
the **Web-public** option for **Who can access the stream?**.

To make an existing stream web-public, follow the instructions to
[change the privacy of a
stream](/help/change-the-privacy-of-a-stream), selecting the
**Web-public** option for **Who can access the stream?**.

## What can logged out visitors do?

Logged out visitors can browse all content in web-public streams,
including using Zulip's [built-in search](/help/search-for-messages)
to find conversations. Logged out visitors can only access
the web-public streams in your organization, and the topics, messages
(including uploaded files) and emoji reactions in those streams.

They **cannot**:

* View streams that are not configured as web-public streams (or see
  whether any such streams exist) without creating an account.
* Send messages.
* React with emoji.
* Participate in polls, or do anything else that might be visible to
  other users.

Logged out visitors have access to a subset of the metadata
information available to any new account in the Zulip organization,
detailed below.

### Information about the organization

* The **Organization settings** and **Stream settings** menus are not
  available to logged out visitors. However, organization settings data is
  required for Zulip to load, and may thus be [accessed via the Zulip API][info-via-api].
* Logged out visitors cannot view [organization statistics](/help/analytics).

[info-via-api]: /help/web-public-streams#information-that-can-be-accessed-via-api-when-web-public-streams-are-enabled

### Information about users

Logged out visitors can see the following information about users who
participate in web-public streams. They do not see this information
about users who do not participate in web-public streams in the Zulip
UI, though they may access it via the Zulip API.

* Name
* Avatar
* Role (e.g. Administrator)
* Join date

The following additional information is not available in the UI for
logged out visitors, but may be accessed without an account via the
Zulip API:

* Configured time zone
* Which user groups a user belongs to

The following information is available to all users with an account,
but not to logged out visitors:

* Presence information, i.e. whether the user is currently online, their status,
  and whether they have set themselves as unavailable.
* Detailed profile information, such as [custom profile
  fields](/help/add-custom-profile-fields).
* Which users are subscribed to which web-public streams.

## Managing abuse

The unfortunate reality is that any service
that allows hosting files visible to the Internet is a potential target for bad
actors looking for places to distribute illegal or malicious content.

In order to protect Zulip organizations from
bad actors, web-public streams have a few limitations designed to make
Zulip an inconvenient target:

* Only users in trusted roles like Moderators can be given permission
  to create web-public streams. This is intended to make it hard for
  an attacker to host malicious content in an unadvertised web-public
  stream in a legitimate organization.
* There are rate limits for unauthenticated access to uploaded
  files, including viewing avatars and custom emoji.

Our aim is to tune anti-abuse protections so that they don't
interfere with legitimate use. Please [contact us](/help/contact-support)
if your organization encounters any problems with legitimate activity caused
these anti-abuse features.

As a reminder, Zulip Cloud organizations are expected to
[moderate content](/help/moderating-open-organizations) to ensure compliance
with Zulip's Rules of Use.

## Caveats

The web-public visitors feature is not yet integrated with Zulip's
live-update system. As a result, a visitor will not see messages that are sent
while Zulip is open until they reload the browser window.

## Related articles

* [Moderating open organizations](/help/moderating-open-organizations)
* [Stream permissions](/help/stream-permissions)
* [Restrict stream creation](/help/configure-who-can-create-streams)
