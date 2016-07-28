Zulip 2016 Roadmap
==================

## Introduction

Zulip has received a great deal of interest and attention since it was
released as free and open source software by Dropbox.  That attention
has come with a lot of active development work from members of the
Zulip community.  From when Zulip was released as open source in late
September 2015 through today (mid-April, 2016), over 300 pull requests
have been submitted to the various Zulip repositories (and over 250
have been merged!), the vast majority of which are submitted by
Zulip's users around the world (as opposed to the small core team that
reviews and merges the pull requests).

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

Update: Neeraj Wahi is leading an effort on to write a [new React
Native iOS app for Zulip](https://github.com/zulip/zulip-mobile) to
replace the old iOS app.

## Core User Experience

This category includes important improvements to the core user
experience that will benefit all users.

* <strike>[Improve missed message notifications to make "reply" work nicely](https://github.com/zulip/zulip/issues/612)</strike>
* [Add support for showing "user is typing" notifications](https://github.com/zulip/zulip/issues/150)
* [Add pretty bubbles for recipients in the compose box](https://github.com/zulip/zulip/issues/595)
* <strike>[Finish and merge support for pinning a few important streams](https://github.com/zulip/zulip/issues/285)</strike>
* [Display stream descriptions more prominently](https://github.com/zulip/zulip/issues/164)
* [Integration inline URL previews](https://github.com/zulip/zulip/issues/406)
* [Add support for managing uploaded files](https://github.com/zulip/zulip/issues/454)
* [Make Zulip onboarding experience smoother for teams not used to topics](https://github.com/zulip/zulip/issues/647).  That specific proposal might not be right but the issue is worth investing time in.

## Ease of setup and onboarding issues

This category focuses on issues users experience when installing a new
Zulip server or setting up a new Zulip realm.

* [Create a web flow for setting up a new realm / the first realm on a new server (currently, it's a command-line process)](https://github.com/zulip/zulip/issues/260)
* [Document or better script solution to rabbitmq startup issues](https://github.com/zulip/zulip/issues/465)
* [Add a mechanism for deleting early test messages](https://github.com/zulip/zulip/issues/135)
* [Merge a supported way to use Zulip in Docker in production
  implementation](https://github.com/zulip/zulip/pull/450).

## Internationalization

The core Zulip UI has been mostly translated into 5 languages;
however, more work is required to make those translations actually
displayed in the Zulip UI for the users who would benefit from them.

* <strike>[Merge support for using translations in Django templates](https://github.com/zulip/zulip/pull/607)</strike>
* <strike>[Add text in handlebars templates to translatable string database](https://github.com/zulip/zulip/issues/726)</strike>
* <strike>[Merge support for translating text in handlebars](https://github.com/zulip/zulip/issues/726)</strike>
* <strike>[Add text in error messages to translatable strings](https://github.com/zulip/zulip/issues/727)</strike>

## User Experience at scale

There are a few parts of the Zulip UI which could benefit from
overhauls designed around making the user experience nice for large
teams.

* [Make the buddy list work better for large teams](https://github.com/zulip/zulip/issues/236)
* [Improve @-mentioning syntax based on stronger unique identifiers](https://github.com/zulip/zulip/issues/374)
* [Show subscriber counts on streams](https://github.com/zulip/zulip/pull/525)
* [Make the streams page easier to navigate with 100s of streams](https://github.com/zulip/zulip/issues/563)
* <strike>[Add support for filtering long lists of streams](https://github.com/zulip/zulip/issues/565)</strike>

## Administration and management

Currently, Zulip has a number of administration features that can be
controlled only via the command line.

* <strike>[Make default streams web-configurable](https://github.com/zulip/zulip/issues/665)</strike>
* <strike>[Make realm emoji web-configurable](https://github.com/zulip/zulip/pull/543)</strike>
* [Make realm filters web-configurable](https://github.com/zulip/zulip/pull/544)
* [Make realm aliases web-configurable](https://github.com/zulip/zulip/pull/651)
* [Enhance the LDAP integration and make it web-configurable](https://github.com/zulip/zulip/issues/715)
* [Add a SAML integration for Zulip](https://github.com/zulip/zulip/issues/716)
* [Improve administrative controls for managing streams](https://github.com/zulip/zulip/issues/425)

## Scalability

Zulip should support 10000 users in a realm and also support smaller
realms in more resource-constrained environments (probably a good
initial goal is working well with only 2GB of RAM).

* [Make the Zulip Tornado service support horizontal scaling](https://github.com/zulip/zulip/issues/445)
* [Make presence system scale well to 10000 users in a realm.](https://github.com/zulip/zulip/issues/728)
* [Support running queue workers multithreaded in production to
  decrease minimum memory footprint](https://github.com/zulip/zulip/issues/34)

## Performance

Performance is essential for a communication tool.  While some things
are already quite good (e.g. narrowing and message sending is speedy),
this is an area where one can always improve.  There are a few known
performance opportunities:

* <strike>[Migrate to faster jinja2 templating engine](https://github.com/zulip/zulip/issues/620)</strike>
* <strike>[Don't load zxcvbn when it isn't needed](https://github.com/zulip/zulip/issues/263)</strike>
* [Optimize the frontend performance of loading the Zulip webapp using profiling](https://github.com/zulip/zulip/issues/714)

## Technology improvements

Zulip should be making use of the best Python/Django tools available.

* [Add support for Zulip running on Python 3](https://github.com/zulip/zulip/issues/256)
* [Add support for changing users' email addresses](https://github.com/zulip/zulip/issues/734)
* [Automatic thumbnailing of uploaded images](https://github.com/zulip/zulip/issues/432)
* [Upgrade Zulip to use Django 1.10 once it is released.  The patches
  needed to run Zulip were merged into mainline Django in Django 1.10,
  so this will mean we don't need to use a fork of Django anymore.](https://github.com/zulip/zulip/issues/3)

## Technical Debt

While the Zulip server has a great codebase compared to most projects
of its size, it takes work to keep it that way.

* [Migrate most web routes to REST API](https://github.com/zulip/zulip/issues/611)
* [Finish purging global variables from the Zulip JavaScript](https://github.com/zulip/zulip/issues/610)
* [Finish deprecating and remove the pre-REST Zulip /send_message API](https://github.com/zulip/zulip/issues/730)
* [Split Tornado subsystem into a separate Django app](https://github.com/zulip/zulip/issues/729)
* [Clean up clutter in the root of the zulip.git repository](https://github.com/zulip/zulip/issues/707)
* [Refactor zulip.css to be broken into components](https://github.com/zulip/zulip/issues/731)

## Deployment and upgrade process

* <strike>[Support backwards-incompatible upgrades to Python libraries](https://github.com/zulip/zulip/issues/717)</strike>
* [Minimize the downtime required in the Zulip upgrade process](https://github.com/zulip/zulip/issues/646)

## Security

* [Add support for 2-factor authentication on all platforms](https://github.com/zulip/zulip/pull/451)
* [Add a retention policy feature that automatically deletes old messages](https://github.com/zulip/zulip/issues/106)
* [Upgrade every Zulip dependency to a modern version](https://github.com/zulip/zulip/issues/1331)
* [The LOCAL_UPLOADS_DIR file uploads backend only supports world-readable uploads](https://github.com/zulip/zulip/issues/320)
* [Add support for stronger security controls for uploaded files](https://github.com/zulip/zulip/issues/320)

## Testing

* [Extend Zulip's automated test coverage to include all API endpoints](https://github.com/zulip/zulip/issues/732)
* [Build automated tests for the client API bindings](https://github.com/zulip/zulip/issues/713)
* [Add Python static type-checking to Zulip using mypy](https://github.com/zulip/zulip/issues/733)
* <strike>[Improve the runtime of Zulip's backend test suite](https://github.com/zulip/zulip/issues/441)</strike>
* <strike>[Use caching to make Travis CI runtimes faster](https://github.com/zulip/zulip/issues/712)</strike>
* [Add automated tests for the production upgrade process](https://github.com/zulip/zulip/issues/306)
* <strike>[Improve Travis CI "production" test suite to catch more regressions](https://github.com/zulip/zulip/issues/598)</strike>

## Development environment

* [Migrate from jslint to eslint](https://github.com/zulip/zulip/issues/535)
* <strike>[Figure out a nice upgrade process for Zulip Vagrant VMs](https://github.com/zulip/zulip/issues/264)</strike>
* [Replace closure-compiler with a faster minifier toolchain](https://github.com/zulip/zulip/issues/693)
* [Add support for building frontend features in React](https://github.com/zulip/zulip/issues/694)
* [Use a JavaScript bundler like webpack](https://github.com/zulip/zulip/issues/695)

## Documentation

* [Significantly expand documentation of the Zulip API and integrating
  with Zulip.](https://github.com/zulip/zulip/issues/672)
* [Expand library of documentation on Zulip's feature set.  Currently
  most documentation is for either developers or system administrators.](https://github.com/zulip/zulip/issues/675)
* [Expand developer documentation with more tutorials explaining how to do
  various types of projects.](https://github.com/zulip/zulip/issues/676)
* [Overhaul new contributor documentation, especially on coding style,
  to better highlight and teach the important pieces.](https://github.com/zulip/zulip/issues/677)
* [Update all screenshots to show the current Zulip UI](https://github.com/zulip/zulip/issues/599)

## Integrations

Integrations are essential to Zulip.  While we currently have a
reasonably good framework for writing new webhook integrations for
getting notifications into Zulip, it'd be great to streamline that
process and make bots that receive messages just as easy to build.

* <strike>[Make it super easy to take screenshots for new webhook integrations](https://github.com/zulip/zulip/issues/658)</strike>
* [Add an outgoing webhook integration system](https://github.com/zulip/zulip/issues/735)
* <strike>[Build a framework to cut duplicated code in new webhook integrations](https://github.com/zulip/zulip/issues/660)</strike>
* [Make setting up a new integration a smooth flow](https://github.com/zulip/zulip/issues/692)
* <strike>[Optimize the integration writing documentation to make writing new
   ones really easy.](https://github.com/zulip/zulip/issues/70)</strike>

## Android app

The Zulip Android app is ahead of the iOS app in terms of feature set,
but there is still a lot of work to do. Most of the things listed below
will eventually apply to the iOS app as well.

* <strike>[Support using a non-zulip.com server](https://github.com/zulip/zulip-android/issues/1)</strike>
* [Support Google authentication with a non-Zulip.com server](https://github.com/zulip/zulip-android/issues/49)
* [Add support for narrowing to @-mentions](https://github.com/zulip/zulip-android/issues/39)
* [Support having multiple Zulip realms open simultaneously](https://github.com/zulip/zulip-android/issues/47)
* <strike>[Build a slick development login page to simplify testing (similar to
  the development homepage on web)](https://github.com/zulip/zulip-android/issues/48)</strike>
* <strike>[Improve the compose box to let you see what you're replying to](https://github.com/zulip/zulip-android/issues/8)</strike>
* [Make it easy to compose messages with mentions, emoji, etc.](https://github.com/zulip/zulip-android/issues/11)
* [Display unread counts and improve navigation](https://github.com/zulip/zulip-android/issues/57)
* <strike>[Hide messages sent to muted topics](https://github.com/zulip/zulip-android/issues/9)</strike>
* [Fill out documentation to make it easy to get started](https://github.com/zulip/zulip-android/issues/58)

## iOS app

Most of the projects listed under Android apply here as well, but it's
worth highlighting some areas where iOS is substantially behind
Android.  The top priority here is recruiting a lead developer for the
iOS app.  Once we have that resolved, we'll expand our ambitions for
the app with more specific improvements.

* [iOS app needs maintainer](https://github.com/zulip/zulip-ios/issues/12)
* <strike>[APNS notifications are broken](https://github.com/zulip/zulip/issues/538)</strike>

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

* <strike>Setup a Zulip server for the Zulip development community</strike>
* Expand the number of core developers able to do code reviews
* <strike>Expand the number of contributors regularly adding features to Zulip</strike>
* Have a successful summer with Zulip's 3 GSOC students
