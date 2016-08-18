# Customize Zulip

Once you've got Zulip setup, you'll likely want to configure it the
way you like.  There are four big things to focus on:

1. [Integrations](#integrations)
2. [Streams and Topics](#streams-and-topics)
3. [Notification settings](#notification-settings)
4. [Mobile and desktop apps](#mobile-and-desktop-apps)

Lastly, read about Zulip's other [great features](#all-other-features), and
then [enjoy your Zulip installation](#enjoy-your-zulip-installation)!

## Integrations

We recommend setting up integrations for the major
tools that your team works with.  For example, if you're a software
development team, you may want to start with integrations for your
version control, issue tracker, CI system, and monitoring tools.

Spend time configuring these integrations to be how you like them --
if an integration is spammy, you may want to change it to not send
messages that nobody cares about (E.g. for the zulip.com trac
integration, some teams find they only want notifications when new
tickets are opened, commented on, or closed, and not every time
someone edits the metadata).

If Zulip doesn't have an integration you want, you can add your own!
Most integrations are very easy to write, and even more complex
integrations usually take less than a day's work to build.  We very
much appreciate contributions of new integrations; see the brief
[integration writing guide](integration-guide.html).


It can often be valuable to integrate your own internal processes to
send notifications into Zulip; e.g. notifications of new customer
signups, new error reports, or daily reports on the team's key
metrics; this can often spawn discussions in response to the data.

## Streams and Topics

If it feels like a stream has too much
traffic about a topic only of interest to some of the subscribers,
consider adding or renaming streams until you feel like your team is
working productively.

Second, most users are not used to topics.  It can require a bit of
time for everyone to get used to topics and start benefitting from
them, but usually once a team is using them well, everyone ends up
enthusiastic about how much topics make life easier.  Some tips on
using topics:

* When replying to an existing conversation thread, just click on the
  message, or navigate to it with the arrow keys and hit "r" or
  "enter" to reply on the same topic
* When you start a new conversation topic, even if it's related to the
  previous conversation, type a new topic in the compose box
* You can edit topics to fix a thread that's already been started,
  which can be helpful when onboarding new batches of users to the platform.

Third, setting default streams for new users is a great way to get
new users involved in conversations before they've accustomed
themselves with joining streams on their own. You can use the
[`set_default_streams`](https://github.com/zulip/zulip/blob/master/zerver/management/commands/set_default_streams.py)
command to set default streams for users within a realm:

```
python manage.py set_default_streams --domain=example.com --streams=foo,bar,...
```

## Notification settings

Zulip gives you a great deal of control
over which messages trigger desktop notifications; you can configure
these extensively in the `/#settings` page (get there from the gear
menu).  If you find the desktop notifications annoying, consider
changing the settings to only trigger desktop notifications when you
receive a PM or are @-mentioned.

## Mobile and desktop apps

Currently, the Zulip Desktop app
only supports talking to servers with a properly signed SSL
certificate, so you may find that you get a blank screen when you
connect to a Zulip server using a self-signed certificate.

The Zulip Android app in the Google Play store doesn't yet support
talking to non-zulip.com servers (and the iOS one doesn't support
Google auth SSO against non-zulip.com servers; there's a design for
how to fix that which wouldn't be a ton of work to implement).  If you
are interested in helping out with the Zulip mobile apps, shoot an
email to zulip-devel@googlegroups.com and the maintainers can guide
you on how to help.

For announcements about improvements to the apps, make sure to join
the zulip-announce@googlegroups.com list so that you can receive the
announcements when these become available.

## All other features

Hotkeys, emoji, search filters,
@-mentions, etc.  Zulip has lots of great features, make sure your
team knows they exist and how to use them effectively.

## Enjoy your Zulip installation!  

If you discover things that you
wish had been documented, please contribute documentation suggestions
either via a GitHub issue or pull request; we love even small
contributions, and we'd love to make the Zulip documentation cover
everything anyone might want to know about running Zulip in
production.

Next: [Maintaining and upgrading Zulip in
production](prod-maintain-secure-upgrade.html).
