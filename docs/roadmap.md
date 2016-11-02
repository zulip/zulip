Zulip 2016 Roadmap
==================

## Introduction

Zulip has received a great deal of interest and attention since it was
released as free and open source software by Dropbox.  That attention
has come with a lot of active development work from members of the
Zulip community.  From when Zulip was released as open source in late
September 2015 through today (early November, 2016), over 1000 pull
requests have been submitted to the various Zulip repositories (and
nearly 1000 have been merged!), the vast majority of which are
submitted by Zulip's users around the world (as opposed to the small
core team that reviews and merges the pull requests).

In any project, there can be a lot of value in periodically putting
together a roadmap detailing the major areas where the project is
hoping to improve.  This can be especially important in an open source
project like Zulip where development is distributed across many people
around the world.  This roadmap is intended to organize a list of the
most important improvements that should be made to Zulip in the
relatively near future.  Our aim is to complete most of these
improvements in 2016.

This document is not meant to constrain in any way what contributions
to Zulip will be accepted; instead, it will be used by the Zulip core
team to prioritize our efforts, measure progress on improving the
Zulip product, hold ourselves accountable for making Zulip improve
rapidly, and celebrate members of the community who contribute to
projects on the roadmap.

If you're someone interested in making a larger contribution to Zulip
and looking for somewhere to start, this roadmap is the best place to
look for substantial projects that will definitely be of value to the
community (if you're looking for a starter project, see the [guide to
getting involved with
Zulip](https://github.com/zulip/zulip#how-to-get-involved-with-contributing-to-zulip)).

We occasionally update this roadmap by adding strikethrough for issues
that have been resolved.

Without further ado, below is the Zulip 2016 roadmap.

## Burning problems

The top problem for the Zulip project is the state of the mobile apps.
The Android app has started seeing rapid progress thanks to a series
of contributions by Lisa Neigut of Recurse Center, and we believe it
is on a good path.  The iOS app has fewer features than Android and
has more bugs, but more importantly is in need of an experienced iOS
developer who has time to drive the project.

Update: Neeraj Wahi is leading an effort to write a [new React Native
iOS app for Zulip](https://github.com/zulip/zulip-mobile) to replace
the old iOS app. We aim to have this launched by early January 2017.

## Core User Experience

This category includes important improvements to the core user
experience that will benefit all users.

* Complete visual redesign (in progress).
* [Provide shorter UI/Keyboard sequence to edit the last
  message](https://github.com/zulip/zulip/issues/1147)
* [Better drafts
  management](https://github.com/zulip/zulip/issues/1717)
* [Make clicking on desktop notifications renarrow
  properly](https://github.com/zulip/zulip/issues/1996)

### Social features

* [Add support for showing "user is typing" notifications, at least
  for private messages](https://github.com/zulip/zulip/issues/150)
* [Support lightweight emoji
  "reactions](https://github.com/zulip/zulip/issues/541)
* [Open graph previews of generic
  websites](https://github.com/zulip/zulip/issues/406)

### Nice to have

* [Add pretty bubbles for recipients in the compose box](https://github.com/zulip/zulip/issues/595)
* [Display stream descriptions more prominently](https://github.com/zulip/zulip/issues/164)
* [Integration inline URL previews](https://github.com/zulip/zulip/issues/406)
* [Add support for managing uploaded files](https://github.com/zulip/zulip/issues/454)
* [Make Zulip onboarding experience smoother for teams not used to topics](https://github.com/zulip/zulip/issues/647).  That specific proposal might not be right but the issue is worth investing time in.

## Ease of setup and onboarding issues

This category focuses on issues users experience when installing a new
Zulip server, setting up a new Zulip realm, or starting to use Zulip.

* [Document or better script solution to rabbitmq startup
  issues](https://github.com/zulip/zulip/issues/465)
* [Add a SAML integration for
  Zulip](https://github.com/zulip/zulip/issues/716)
* [Add a mechanism for deleting early test messages (e.g.,
  administrators can hard-delete
  messages)](https://github.com/zulip/zulip/issues/135)
* [Move Zulip's prompt for permission to display notifications to be
  manually triggered](https://github.com/zulip/zulip/issues/1189)
* [Fix our desktop notifications defaults to not be auto-on for
  streams](https://github.com/zulip/zulip/issues/1706)

### Nice to have

* [Merge a supported way to use Zulip in Docker in production
  implementation](https://github.com/zulip/zulip/pull/450).

## Real-time sync

This category focuses on notifications and keeping the user up-to-date
with their community.

* [Notification bot advertisements for new streams don’t handle stream
  renames](https://github.com/zulip/zulip/issues/426)
* [Avatar/name changes don’t propagate to already-sent
  messages](https://github.com/zulip/zulip/issues/1932)
* [Advance the pointer / where we load the user to based on unread
  counts in home view](https://github.com/zulip/zulip/issues/1529)

## Administration and management

Currently, Zulip has a number of administration features that can be
controlled only via the command line.

* [Statistics display for realm and server
  administrators](https://github.com/zulip/zulip/issues/2052)
* [Keep track of which users added which realm
  emoji](https://github.com/zulip/zulip/issues/984)
* [Add setting to enable any user to add new realm
  emoji](https://github.com/zulip/zulip/issues/978)

### Nice to have

* [Make realm filters web-configurable](https://github.com/zulip/zulip/pull/544)
* [Make realm aliases web-configurable](https://github.com/zulip/zulip/pull/651)
* [Enhance the LDAP integration and make it web-configurable](https://github.com/zulip/zulip/issues/715)
* [Improve administrative controls for managing streams](https://github.com/zulip/zulip/issues/425)

## Scalability and performance

Zulip should support 10000 users in a realm and also support smaller
realms in more resource-constrained environments (probably a good
initial goal is working well with only 2GB of RAM). Scaling includes
improving the user experience for large teams. Performance is also
essential, and some things are already quite good (e.g., narrowing and
message sending is speedy).

* [Make the Zulip Tornado service support horizontal
  scaling](https://github.com/zulip/zulip/issues/445)

### Nice to have

* [Make presence system scale well to 10000 users in a
  realm.](https://github.com/zulip/zulip/issues/728)
* [Support running queue workers multithreaded in production to
  decrease minimum memory
  footprint](https://github.com/zulip/zulip/issues/34)
* [Optimize the frontend performance of loading the Zulip webapp using
  profiling](https://github.com/zulip/zulip/issues/714)
* [Improve @-mentioning syntax based on stronger unique
  identifiers](https://github.com/zulip/zulip/issues/374)
* [Show subscriber counts on
  streams](https://github.com/zulip/zulip/pull/525)

## Technology improvements

Zulip should be making use of the best Python/Django tools available.

* [Add support for Zulip running purely on Python
  3](https://github.com/zulip/zulip/issues/256)
* [Automatic thumbnailing of uploaded images' previews to save
  bandwidth](https://github.com/zulip/zulip/issues/432)
* [Upgrade Zulip to use Django 1.10 once it is released.  The patches
  needed to run Zulip were merged into mainline Django in Django 1.10,
  so this will mean we don't need to use a fork of Django
  anymore.](https://github.com/zulip/zulip/issues/3)
* [Upgrade and remove from codebase all of our vendored JS
  libraries](https://github.com/zulip/zulip/issues/1709)

### Nice to have

* [Add support for changing users' email
  addresses](https://github.com/zulip/zulip/issues/734)

## Technical Debt

While the Zulip server has a great codebase compared to most projects
of its size, it takes work to keep it that way.

* [Migrate most web routes to REST API](https://github.com/zulip/zulip/issues/611)
* [Finish purging global variables from the Zulip JavaScript](https://github.com/zulip/zulip/issues/610)
* [Split Tornado subsystem into a separate Django app](https://github.com/zulip/zulip/issues/729)
* [Refactor zulip.css to be broken into components](https://github.com/zulip/zulip/issues/731)

## Deployment and upgrade process

* [Minimize the downtime required in the Zulip upgrade process](https://github.com/zulip/zulip/issues/646)

## Security

* [Add support for 2-factor authentication on all
  platforms](https://github.com/zulip/zulip/pull/451)
* [Add support for stronger security controls for uploaded files (The
  LOCAL_UPLOADS_DIR file uploads backend only supports world-readable
  uploads)](https://github.com/zulip/zulip/issues/320)
* [Fix requirement to set a password when creating account via
  Google](https://github.com/zulip/zulip/issues/1633) (Basically
  requires making the a re-prompt-for-password flow for things like
  “show my my API key” that supports other auth mechanisms)
* [Add a retention policy feature that automatically deletes old
  messages](https://github.com/zulip/zulip/issues/106)
* [Add UI for viewing and cancelling open Zulip
  invitations](https://github.com/zulip/zulip/issues/1180)

### Nice to have

* [Upgrade every Zulip dependency to a modern
  version](https://github.com/zulip/zulip/issues/1331)

## Testing

* [Extend Zulip's automated test coverage to include all API endpoints](https://github.com/zulip/zulip/issues/732)
* [Build automated tests for the client API bindings](https://github.com/zulip/zulip/issues/713)
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

* [Expand library of documentation on Zulip's feature set.  Currently
  most documentation is for either developers or system
  administrators.](https://github.com/zulip/zulip/issues/675)
* [Expand developer documentation with more tutorials explaining how
  to do various types of
  projects.](https://github.com/zulip/zulip/issues/676)

## Integrations

Integrations are essential to Zulip.  While we currently have a
reasonably good framework for writing new webhook integrations for
getting notifications into Zulip, it'd be great to streamline that
process and make bots that receive messages just as easy to build.

* [Add an outgoing webhook integration system](https://github.com/zulip/zulip/issues/735)
* [Make setting up a new integration a smooth flow](https://github.com/zulip/zulip/issues/692)
* [Default new incoming webhooks to permissions-limited incoming webhook bots](https://github.com/zulip/zulip/issues/2186)
* [Display how Zulip displays bot names to distinguish them from human users](https://github.com/zulip/zulip/issues/1107)

## Android app

The Zulip Android app is ahead of the iOS app in terms of feature set,
but there is still a lot of work to do. Most of the things listed below
will eventually apply to the iOS app as well.

* [Add support for narrowing to
  @-mentions](https://github.com/zulip/zulip-android/issues/39)
* [Support having multiple Zulip realms open
  simultaneously](https://github.com/zulip/zulip-android/issues/47)

## Server/webapp support for mobile

To support a great mobile experiences, we need to make some
improvements in Zulip core.

* [Push notifications bouncer service for GCM and
  APNS](https://github.com/zulip/zulip/issues/1767)
* [A slick process for doing mobile login without typing your password
  on your phone](https://github.com/zulip/zulip/issues/2185)
* [`@here` mention support (that doesn’t spam people not currently
  online, i.e. no email/push
  notifications)](https://github.com/zulip/zulip/issues/2183)
* [Fix sending messages from mobile
  web](https://github.com/zulip/zulip/issues/2184)

## Desktop apps

The top goal for the desktop apps is to rebuild it in a modern
toolchain so that it's easy for a wide range of developers to
contribute to the apps. The new [cross-platform
app](https://github.com/zulip/zulip-electron) is implemented in
[Electron](http://electron.atom.io/), a framework (maintained by
GitHub) that uses Chromium and Node.js, so Zulip developers only need
to write HTML, CSS, and JavaScript. The new Zulip app is in alpha as of
early August 2016.

* Migrate platform from QT/webkit to Electron
* Desktop app doesn't recover well from entering the wrong Zulip server
* [Support having multiple Zulip realms open simultaneously](https://github.com/zulip/zulip-electron/issues/1)
* Build an efficient process for testing and releasing new versions of
  the desktop apps

## Community

These don't get GitHub issues since they're not technical projects,
but they are important goals for the project.

* Expand the number of core developers able to do code reviews
* Have a successful season with Zulip's Outreachy participants

## Internationalization

The core Zulip UI has been mostly translated into 5 languages, and
those translations display in the Zulip UI; we don't currently have
any localization/internationalization work on the roadmap.

## Development environment -- nice to have

* [Migrate from jslint to eslint](https://github.com/zulip/zulip/issues/535)
* [Replace closure-compiler with a faster minifier toolchain](https://github.com/zulip/zulip/issues/693)
* [Add support for building frontend features in React](https://github.com/zulip/zulip/issues/694)
* [Use a JavaScript bundler like webpack](https://github.com/zulip/zulip/issues/695)
