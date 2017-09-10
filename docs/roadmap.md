Zulip Roadmap
=============

## Introduction

Zulip has received a great deal of interest and attention since it was
released as free and open source software by Dropbox.  That attention
has come with a lot of active development work from members of the
Zulip community.  From when Zulip was released as open source in late
September 2015 through today (early November, 2016), more than 150
people have contributed over 1000 pull requests to the various Zulip
repositories, the vast majority of which were submitted by Zulip's
users around the world (as opposed to the small core team that reviews
and merges the pull requests).

In any project, there can be a lot of value in periodically putting
together a roadmap detailing the major areas where the project is
hoping to improve.  This can be especially important in an open source
project like Zulip, where development is distributed across many people
around the world.  This roadmap is intended to organize a list of the
most important improvements that should be made to Zulip in the
relatively near future.  Our aim is to complete most of these
improvements by February 2017 and then prepare a new roadmap then.

This document is not meant to constrain in any way what contributions
to Zulip will be accepted; instead, it will be used by the Zulip core
team to prioritize our efforts, measure progress on improving the
Zulip product and hold ourselves accountable for making Zulip improve
rapidly.

This roadmap is the best place for contributors to look for
substantial projects that will definitely be of value to the community
(if you're looking for a starter project, see the
[guide to getting involved with Zulip](https://github.com/zulip/zulip#how-to-get-involved-with-contributing-to-zulip)).

We periodically update this roadmap by adding strikethrough to issues
that have been resolved, but the linked GitHub issues are the most
up-to-date source for that information.

Update: As of May 2017, we are approaching the point where we need to
update the roadmap due to much of it being completed.

Without further ado, below is the current Zulip roadmap.

## Major projects

There are 2 huge projects that Zulip is working on right now that are
too big to have a coherent GitHub issue:

* We are working with a world-class designer on a major visual
redesign of the Zulip webapp.  Already complete is completely
redesining the streams and settings UIs, logged-out pages, and various
other major components.

* We are writing a
[new React Native iOS app for Zulip](https://github.com/zulip/zulip-mobile)
to replace the old iOS app.  The new app is progressing rapidly, but
is not yet feature complete.  We expect it to be in the app store in
May 2017.

## Core User Experience

* <strike>[Provide shorter UI/Keyboard sequence to edit the last
  message](https://github.com/zulip/zulip/issues/1147)</strike>
* <strike>[Better drafts
  management](https://github.com/zulip/zulip/issues/1717)</strike>
* <strike>[Make clicking on desktop notifications renarrow
  properly](https://github.com/zulip/zulip/issues/1996)</strike>
* [Add pretty bubbles for recipients in the compose box](https://github.com/zulip/zulip/issues/595)
* <strike>[Make right sidebar buddy list UI scale well to large
  teams](https://github.com/zulip/zulip/issues/236)</strike>
* [Display stream descriptions more prominently](https://github.com/zulip/zulip/issues/164)
* <strike>[Add support for managing uploaded files](https://github.com/zulip/zulip/issues/454)</strike>

## Social features

* <strike>[Add support for showing "user is typing" notifications, at least
  for private messages](https://github.com/zulip/zulip/issues/150)</strike>
* <strike>[Support lightweight emoji
  "reactions"](https://github.com/zulip/zulip/issues/541)</strike>
* <strike>[Open graph previews of generic
  websites](https://github.com/zulip/zulip/issues/406)</strike>
* <strike>[Add a "join Zulip chat" badge for projects that use Zulip to
  document that nicely](https://github.com/zulip/zulip/issues/2270)</strike>

## Real-time sync

The overall goal is to eliminate the few known issues where Zulip does
not provide a seamless real-time sync experience.

* <strike>[Notification bot advertisements for new streams don’t handle stream
  renames](https://github.com/zulip/zulip/issues/426)</strike>
* <strike>[Avatar/name changes don’t propagate to already-sent
  messages](https://github.com/zulip/zulip/issues/1932)</strike>
* [Advance the pointer / where we load the user to based on unread
  counts in home view](https://github.com/zulip/zulip/issues/1529)
* [Fix the known bug where messages could be incorrectly marked as read](https://github.com/zulip/zulip/issues/2091)

## Onboarding issues

This category focuses on issues users experience when installing a new
Zulip server, setting up a new Zulip realm, or starting to use Zulip.

* [Move Zulip's prompt for permission to display notifications to be
  manually triggered](https://github.com/zulip/zulip/issues/1189)
* <strike>[Add a mechanism for deleting early test messages (e.g.,
  administrators can hard-delete
  messages)](https://github.com/zulip/zulip/issues/135)</strike>
* <strike>[Allow customizing emails when inviting new users](https://github.com/zulip/zulip/pull/1409)</strike>

## Production installation issues

* <strike>[Document or better script solution to rabbitmq startup
  issues](https://github.com/zulip/zulip/issues/465)</strike>
* [Merge a supported way to use Zulip in Docker in production
  implementation](https://github.com/zulip/zulip/pull/450).

## Administration and management

* <strike>[Make list of allowed domains web-configurable](https://github.com/zulip/zulip/issues/651)</strike>
* <strike>[Statistics display for realm and server
  administrators](https://github.com/zulip/zulip/issues/2052)</strike>
* <strike>[Keep track of which users added which realm
  emoji](https://github.com/zulip/zulip/issues/984)</strike>
* <strike>[Add setting to enable any user to add new realm
  emoji](https://github.com/zulip/zulip/issues/978)</strike>
* <strike>[Make realm filters web-configurable](https://github.com/zulip/zulip/pull/544)</strike>
* [Improve administrative controls for managing streams](https://github.com/zulip/zulip/issues/3783)
* [Enhance the LDAP integration and make it web-configurable](https://github.com/zulip/zulip/issues/715)
* [Add a SAML integration for
  Zulip](https://github.com/zulip/zulip/issues/716)

## Scalability and performance

Scalability and performance are not currently major problems for
Zulip; it already scales well to thousands of users and is
significantly faster than proprietary alternatives.  So, this is not a
major focus area for the project.

* [Make the Zulip Tornado service support horizontal
  scaling](https://github.com/zulip/zulip/issues/445)
* [Make presence system scale well to 10000 users in a
  realm.](https://github.com/zulip/zulip/issues/728)
* <strike>[Support running queue workers multithreaded in production to
  decrease minimum memory</strike>
  footprint](https://github.com/zulip/zulip/issues/34)
* [Improve @-mentioning syntax based on stronger unique
  identifiers](https://github.com/zulip/zulip/issues/374)

## Technology improvements

* <strike>[Add support for Zulip running purely on Python
  3](https://github.com/zulip/zulip/issues/256)</strike>
* [Automatic thumbnailing of uploaded images' previews to save
  bandwidth](https://github.com/zulip/zulip/issues/432)
* <strike>[Upgrade Zulip to use Django 1.10.  The patches
  needed to run Zulip were merged into mainline Django in Django 1.10,
  so this will mean we don't need to use a fork of Django
  anymore.](https://github.com/zulip/zulip/issues/3)</strike>
* [Upgrade and remove from codebase all unnecessarily vendored JS
  libraries](https://github.com/zulip/zulip/issues/1709)
* <strike>[Add support for changing users' email
  addresses](https://github.com/zulip/zulip/issues/734)</strike>
* <strike>[Migrate from jslint to eslint](https://github.com/zulip/zulip/issues/535)</strike>
* [Replace the slow closure-compiler based static asset toolchain](https://github.com/zulip/zulip/issues/693)
* [Use a modern JavaScript bundler like webpack](https://github.com/zulip/zulip/issues/695)
* [Add support for building frontend features in something like React](https://github.com/zulip/zulip/issues/694)

## Technical Debt

While the Zulip server has a great codebase compared to most projects
of its size, it takes work to keep it that way.

* <strike>[Migrate most web routes to REST API](https://github.com/zulip/zulip/issues/611)</strike>
* <strike>[Split Tornado subsystem into a separate Django app](https://github.com/zulip/zulip/issues/729)</strike>
* [Refactor zulip.css to be broken into components](https://github.com/zulip/zulip/issues/731)

## Security

* [Add support for 2-factor authentication on all
  platforms](https://github.com/zulip/zulip/pull/1747)
* [Add support for stronger security controls for uploaded files (The
  LOCAL_UPLOADS_DIR file uploads backend only supports world-readable
  uploads)](https://github.com/zulip/zulip/issues/320)
* <strike>[Fix requirement to set a password when creating account via
  Google](https://github.com/zulip/zulip/issues/1633)</strike>
* [Add a retention policy feature that automatically deletes old
  messages](https://github.com/zulip/zulip/issues/106)
* [Add UI for viewing and cancelling open Zulip
  invitations](https://github.com/zulip/zulip/issues/1180)

## Testing

* <strike>[Extend Zulip's automated test coverage to include all API
  endpoints](https://github.com/zulip/zulip/issues/1441)</strike>
* <strike>[Build automated tests for the client API bindings](https://github.com/zulip/zulip/issues/713)</strike>
* [Add automated tests for the production upgrade process](https://github.com/zulip/zulip/issues/306)

## Documentation

* [Add an in-app mechanism for updating users about new Zulip
  features](https://github.com/zulip/zulip/issues/2187)
* [Significantly expand documentation of the Zulip API and integrating
  with Zulip.](https://github.com/zulip/zulip/issues/672)
* [Write a visual design / frontend style guide for
  Zulip](https://github.com/zulip/zulip/issues/979)
* [Update all screenshots to show the current Zulip
  UI](https://github.com/zulip/zulip/issues/599)

### Nice to have

* <strike>[Expand library of documentation on Zulip's feature set.  Currently
  most documentation is for either developers or system
  administrators.](https://github.com/zulip/zulip/issues/675)</strike>

## Integrations and bots

Integrations are essential to Zulip.  While we currently have a
reasonably good framework for writing new webhook integrations for
getting notifications into Zulip, it'd be great to streamline that
process and make bots that receive messages just as easy to build.

* <strike>[Add an outgoing webhook integration system](https://github.com/zulip/zulip/issues/735)</strike>
* [Make setting up a new integration a smooth flow](https://github.com/zulip/zulip/issues/692)
* <strike>[Default new incoming webhooks to permissions-limited incoming webhook
  bots](https://github.com/zulip/zulip/issues/2186)</strike>
* <strike>[Change how Zulip displays bot names to distinguish them from human
  users](https://github.com/zulip/zulip/issues/1107)</strike>

## Android app

* <strike>[Add support for narrowing to
  @-mentions](https://github.com/zulip/zulip-android/issues/39)</strike>
* [Support having multiple Zulip realms open
  simultaneously](https://github.com/zulip/zulip-android/issues/47)

## iOS app

For the new
[React Native iOS app](https://github.com/zulip/zulip-mobile), the
major goal for it is to be released into the app store.  Since it is
moving quickly, we're
[tracking its roadmap via GitHub milestones](https://github.com/zulip/zulip-mobile/milestones).

## Server/webapp support for mobile

To support a great mobile experiences, we need to make some
improvements in the Zulip server.

* [Push notifications bouncer service for GCM and
  APNS](https://github.com/zulip/zulip/issues/1767)
* [A slick process for doing mobile login without typing your password
  on your phone](https://github.com/zulip/zulip/issues/2185)
* [`@here` mention support (that doesn’t spam people not currently
  online, i.e. no email/push
  notifications)](https://github.com/zulip/zulip/issues/2183)
* <strike>[Fix sending messages from mobile
  web](https://github.com/zulip/zulip/issues/2184)</strike>

## Desktop apps

The new
[cross-platform desktop app](https://github.com/zulip/zulip-electron)
is implemented in [Electron](http://electron.atom.io/), and primarily
needs work on installer tooling to finish replacing the old app.

* Finish releasing the Electron app to replace the old desktop app
* [Support having multiple Zulip realms open
  simultaneously](https://github.com/zulip/zulip-electron/issues/1)

## Community

These don't get GitHub issues since they're not technical projects,
but they are important goals for the project.

* <strike>Expand the number of core developers able to do code reviews</strike>
* <strike>Have a successful season with Zulip's Outreachy participants</strike>
* <strike>Have a successful season with Google Code In.</strike>
