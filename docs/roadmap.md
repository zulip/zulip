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

* [Add pretty bubbles for recipients in the compose box](https://github.com/zulip/zulip/issues/595)
* [Display stream descriptions more prominently](https://github.com/zulip/zulip/issues/164)

## Social features

## Real-time sync

The overall goal is to eliminate the few known issues where Zulip does
not provide a seamless real-time sync experience.

* [Advance the pointer / where we load the user to based on unread
  counts in home view](https://github.com/zulip/zulip/issues/1529)
* [Fix the known bug where messages could be incorrectly marked as read](https://github.com/zulip/zulip/issues/2091)

## Onboarding issues

This category focuses on issues users experience when installing a new
Zulip server, setting up a new Zulip realm, or starting to use Zulip.

* [Move Zulip's prompt for permission to display notifications to be
  manually triggered](https://github.com/zulip/zulip/issues/1189)
* [Add a mechanism for deleting early test messages (e.g.,
  administrators can hard-delete
  messages)](https://github.com/zulip/zulip/issues/135)

## Production installation issues

* [Merge a supported way to use Zulip in Docker in production
  implementation](https://github.com/zulip/zulip/pull/450).

## Administration and management

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
  decrease minimum memory
  footprint](https://github.com/zulip/zulip/issues/34)</strike>
* [Improve @-mentioning syntax based on stronger unique
  identifiers](https://github.com/zulip/zulip/issues/374)

## Technology improvements

* <strike>[Add support for Zulip running purely on Python
  3](https://github.com/zulip/zulip/issues/256)</strike>
* [Automatic thumbnailing of uploaded images' previews to save
  bandwidth](https://github.com/zulip/zulip/issues/432)
* [Upgrade and remove from codebase all unnecessarily vendored JS
  libraries](https://github.com/zulip/zulip/issues/1709)
* [Replace the slow closure-compiler based static asset toolchain](https://github.com/zulip/zulip/issues/693)
* [Use a modern JavaScript bundler like webpack](https://github.com/zulip/zulip/issues/695)
* [Add support for building frontend features in something like React](https://github.com/zulip/zulip/issues/694)

## Technical Debt

While the Zulip server has a great codebase compared to most projects
of its size, it takes work to keep it that way.

* [Migrate most web routes to REST API](https://github.com/zulip/zulip/issues/611)
* [Refactor zulip.css to be broken into components](https://github.com/zulip/zulip/issues/731)

## Security

* [Add support for 2-factor authentication on all
  platforms](https://github.com/zulip/zulip/pull/1747)
* [Add support for stronger security controls for uploaded files (The
  LOCAL_UPLOADS_DIR file uploads backend only supports world-readable
  uploads)](https://github.com/zulip/zulip/issues/320)
* [Fix requirement to set a password when creating account via
  Google](https://github.com/zulip/zulip/issues/1633)
* [Add a retention policy feature that automatically deletes old
  messages](https://github.com/zulip/zulip/issues/106)
* [Add UI for viewing and cancelling open Zulip
  invitations](https://github.com/zulip/zulip/issues/1180)

## Testing

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

## Integrations and bots

Integrations are essential to Zulip.  While we currently have a
reasonably good framework for writing new webhook integrations for
getting notifications into Zulip, it'd be great to streamline that
process and make bots that receive messages just as easy to build.

* [Add an outgoing webhook integration system](https://github.com/zulip/zulip/issues/735)
* [Make setting up a new integration a smooth flow](https://github.com/zulip/zulip/issues/692)
* [Default new incoming webhooks to permissions-limited incoming webhook
  bots](https://github.com/zulip/zulip/issues/2186)

## Android app

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

