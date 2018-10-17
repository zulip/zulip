# Custom Apps

## Definition

Zulip defines a "**custom app**" to be a piece of code that
runs in the Zulip ecosystem, but which is not part of the
core Zulip codebase.  Custom apps are mostly synonymous
with "bots" and "integrations" in the Zulip ecosystem.  We currently
do not support any kind of browser plugin model.

## Problem statement

Zulip wants to enable people in the world to author custom apps
with the following goals in mind:

- Simple custom apps should be simple to write and deploy.
- Custom app authors should be able to easily distribute their work.
- Zulip should provide deployment support for mature, general-purpose bots,
ideally either within organizations (a Zulip admin can vet their own
custom apps and easily deploy them across upgrade cycles)
or across organizations (custom apps get distributed with the Zulip
tarball).

This document describes Zulip's current infrastructure, as
well as laying out a roadmap for some future features.

## A quick note on bots/integrations

As noted earlier, a **custom app** is just a generic term for
what we often call bots or integrations.  We recognize that
bots and integrations can have different connotations.  A bot
typically spends most of its time responding to Zulip
messages.  An integration usually represents an app
that interacts with some large third party system like an issue
tracker.  We will use both terms in this document in an informal
sense, but from an architecture standpoint, we treat bots and
integrations as essentially two shades of the same color.  Many
integrations are implemented as "bots."  Likewise, any bot that
does stuff outside of Zulip acts as an "integration."

Since the line between what a "bot" is and what an "integration"
is can get very blurry, we try to be informal about
"bots/integrations" and more formal
about how "custom apps" actually function within the system.

## Categories of custom apps

### Stimulus/response and read/write

At the end of the day, most useful apps respond to some
stimulus and produce a response.  In the Zulip universe, Zulip
can be the source of the stimulus, or the target of the response,
or both.  Along those lines, we divide custom apps into
these three types:

- A **Zulip Reader** uses activity on Zulip to stimulate an external
response.  An example here would be a follow-up bot that sees
messages with the alert word "@todo" on a stream and then
adds a task to a third party todo-list tool.

- A **Zulip Writer** reacts to external stimuli and generates
Zulip responses.  An example here might be a build bot that
gets triggered by an automated code build finishing and then
writes "build finished" to a Zulip stream.

- A **Zulip Read/Writer** reacts to a stimulus from Zulip by
responding to Zulip.  An example here would be a math bot
that sees a message saying "compute 2+2" and responds with
"2+2=4" on the same stream or back to the user in a PM.

The above three classifications represent kind of a Zulip-centric
view of the universe, but we should put ourselves in the shoes
of somebody "out in the world."

- A **World Reader** is an app that gets some stimulus from
the outside world and produces a response in Zulip.  (So, a world
reader is a Zulip writer.)

- A **World Writer** is an app that gets some stimulus from
Zulip and produces a response in the outside world.  (So, a world
writer is a Zulip reader.)

Some things are a little outside of the scope of this document.
We could plausibly extend Zulip some day to host **World Reader/Writer**
apps that don't even write Zulip messages but simply use
Zulip as a kind of middleware platform.

More in the short term, we will have custom apps that may
read/write from multiple sources.  For example, a meeting bot may
take input from both a cron job and a Zulip stream, and it may
write to both a Zulip stream and a third party calendar tool.  For
the scope of this document, we won't spend a lot of time talking
about how to build these types of apps, but we are aware that
any solution needs to accommodate multiple sources and targets.

### World Reader/Zulip Reader

Finally, we set the stage for how we talk about custom apps in
terms of these two broad categories:

- A **World Reader** responds to stimuli from the outside world (and
typically produces a response in Zulip).
- A **Zulip Reader** responds to stimuli from Zulip conversations (and
typically produces a response in the outside world).

Again, we recognize that there can be overlap between those two
categories for complex custom apps, but we mostly leave it as
an exercise for the reader how to implement those apps.

### Other classifications

We discussed one dimension for classifying custom apps, which
is whether they are world-readers or Zulip-readers.  Here we cover
a few other classification schemes briefly:

- **Generality** Does the custom app have a specific use case or
a general one?  The spectrum here could run from a bot that Alice runs
to update a text file on her laptop (specific) to a Twitter Bot
that is optionally deployed on all Zulip realms (general).
- **Authorship** Who wrote the custom app?  Was it written by
contributors to the Zulip project?
- **Maturity** How well tested is the custom app?  Is it just a prototype?
Has it been sanctioned by an open source community?  Has it been vetted
by Zulip developers?
- **Deployment** Where does the custom app run?  Does it run on Alice's
laptop?  Does it run on a Zulip server?  Does it run as a plugin on third
party infrastructure?
- **Authorization** What streams are the custom app allowed to read
and write from?  Which users can the custom app interact with?
- **Identity** How does the custom app identify itself on Zulip?  How
does it identify itself to the outside world?
- **Third party** We call the non-Zulip target or source of a custom app
the "world."  The "world" could be almost anything, ranging from an
electronic device or text file to a large third-party system like Twitter
or GitHub.

A lot of the classification schemes are interrelated.  Here are some examples:

- For specific-purpose custom apps, authors may be happy to just deploy
them on their own hardware.  For general-use custom apps, authors may want
to have them deployed on the Zulip server with super-user capabilities.
- As a custom app becomes more well-tested and well-vetted, the author
will likely upgrade its deployment over time.  At first the author may
run the custom app on their laptop, then they may find dedicated
hardware, and then finally they contribute the app to the Zulip
project so that Zulip admins can deploy the app on Zulip servers.
- The nature of the third party will influence the deployment strategy. If
I have a little home-grown gadget that can turn off the lights in my kitchen, I may
run a custom app on my laptop that reads my PMs for "turn-off-the-light"
messages.  If I write a generic custom app that needs to update a third
party corporate system based on Zulip events, I may want to deploy code
to a public webserver or try to get my code to be part of the
Zulip project itself.

## World Reader

A **World Reader** custom app is an app that responds to stimuli
from the world outside of Zulip.  It typically functions as a **Zulip
Writer** and posts some kind of message to a Zulip stream or user to
alert people of world events.  Here are some example stimuli:

- A Travis build finishes.
- Somebody tweets on Twitter.
- A hardware sensor notices a temperature increase.
- A pull request is submitted to GitHub.
- A cron job gets started on your laptop to send a reminder.
- Nagios detects a system anomaly.

Setting aside issues of how a custom app is constructed or deployed,
you basically have to solve these problems:
- Detect events.
- Translate events into Zulip messages.
- Post the messages to Zulip.

### Zulip integrations

Zulip actually supports a bunch of integrations out-of-the-box that
perform as **World Readers**.

The [three different integration models](https://zulipchat.com/api/integrations-overview#sending-content-into-zulip)
basically differ in where they perform the main functions of a
**World Reader**.

#### Incoming webhook integrations

In an **incoming webhook** integration, the deployment model is usually this::

**3rd party hardware**:
- detect event
- send data to Zulip webhook

**Zulip**:
- support webhook endpoint
- translate event to messages
- internally post messages


One current limitation of our system is that we don't have a great way
to deploy prototypes of webhook-based custom apps before Zulip has
vetted the translation and added an official endpoint.
Maybe we could set up some kind of webserver that can run translation
code outside of Zulip and externally post the messages, and we
could think about how to structure the code so that it is easy to
eventually turn it into a Zulip-hosted integration.

#### Python scripts

In script integrations, the deployment model is usually this:

**Custom app author's hardware**:
- detect event by polling a third party system
- translate event in the script
- externally post messages

These type of integrations are typically easy to prototype, but they
can be harder to deploy in production settings, since we rely on the
authors to run their own scripts.

In some cases authors might want to at least move the translation/posting
code to live on Zulip, by contributing that code to Zulip as a server-side
integration.  Then, there would still be the challenge of detecting events
in the third party system, where maybe the user submits a patch to the
third party as well.

#### Plugin integrations

In plugin integrations, the deployment model is usually this:

**Third party system (driver)**:
- detect event

**Third party system (plugin)**:
- further detect/triage event
- translate event
- externally post to Zulip

For third parties that have a plugin model, there are often other issues at
play, like the plugins may need to be written in a non-Python language like
Ruby.  There are probably still some scenarios, however, where a lot of the
logic for translation could be moved to a Zulip-side integration, and then we
supply very thin client code for the plugin.

## Zulip Reader

A **Zulip Reader** custom app gets stimuli from Zerver itself. Most
**Zulip Reader** apps are packaged/advertised more as what people commonly call
"bots" than as "integrations." (But sometimes what is currently a "bot" should really
be deployed more like an "integration" in an ideal Zulip universe.)

Example custom **Zulip Reader** apps can be serious or whimsical.

**Serious**

- A user tags a message with an alert word like `@followup` or `@ticket`.
- A user needs help computing something, like a simple math expression
or a timezone conversion.
- A **World Reader** custom app posts something to a Zulip stream that we
want to cross-post to another external system.
- A user wants the custom app to query the outside world, like look up the
weather or search Wikipedia.
- A bot collects RSVPs for an event.
- A bot conducts a user survey.

**Whimsical**

- A user wants to see a random quote of the day or a random cat fact.
- A user wants to tell the office telepresence robot to "turn left."

Setting aside whether a custom app is performing a serious or whimsical
function, there are a few different types of **Zulip Readers**:

- Some readers will do simple local computations and post right back to Zulip.
- Some readers will do more expensive/web-related computations like searching
Wikipedia, but then post right back to Zulip.
- Some readers will mutate the outside world in some way, like posting
messages to third party APIs or controlling hardware.
- Some readers will do some combination of the prior bullets.

## Deployment issues

Zulip currently provides only minimal deployment support for **Zulip
Reader** custom apps:

- It ships with a few native server-side bots like the welcome bot and
the notifications bot.  (These are nice to have, but they are so tightly
integrated into the Zulip core that they don't act as great examples for
future app authors, and they are not easy to extend/customize.)
- Zulip does ship an API client that can conveniently read a `.zuliprc`
file, poll for incoming messages/events, and post new messages to the Zulip server.

### Local deployment

If you download the API client and write a bot that reads from Zulip,
you face the following challenges if you deploy your code on your own
devices:

- It can be difficult to keep the app running 24/7.
- You may have latency issues connecting to the server.
- If you want super-user permissions, you have to secure the API key.
- Without integration to the Zulip server, the app may spin needlessly during upgrades.
- If you've written a personal-use bot, it can be difficult to distribute
code to your friends and have them be able to deploy it.
- If you've written a general-use bot, it may be difficult to persuade your
admin to give you a superuser account.

We want to make it easier to deploy **Zulip Readers** on
Zulip hardware.  The following document talks about how we want to enable this
from a code structuring standpoint:

[Writing contrib bots](https://github.com/zulip/python-zulip-api/blob/master/zulip_bots/README.md)

This document, on the other hand, is more about designing the Zulip backend
system to support eventual deployment of reader apps on the Zulip server.

Before we talk about server-side apps, we should consider an intermediate
solution.

### Non-Zulip dedicated hardware

There are some scenarios, mostly with general-purpose "serious" custom
apps, where an app author might use the following development process:

- Create a prototype and deploy it locally.
- Publicize the app and deploy it on non-Zulip hardware.
- Contribute the app to the Zulip distribution, so that admins can run it Zulip-side.

To give a concrete example, let's say that I work for a company that is
building an issue tracker, and we want to offer Zulip support.  I would
start by writing a **Zulip Reader** that scans for the alert word `@ticket`
on certain public Zulip streams, and part of that app would have logic
to post to my company's issue-tracking API.

Once I'm confident in my prototype, I will probably run it on dedicated
company hardware that might already have tight physical security, 24/7
IT monitoring, etc.

But what if I don't have this kind of infrastructure available to me?
Typically what I will do instead is rent time on some kind of hosting
service.  Some hosting platforms are basically just remote Unix
systems, but others are more oriented toward hosting web apps.

Zulip's current roadmap assumes that authors will likely gravitate
toward web-based solutions (even if it's just running a web server
on their own Unix host in the cloud).

Zulip intends to offer support for "outgoing webhooks."  The term
"outgoing webhook" can be confusing, depending on your perspective,
but it simply means that an HTTP request is outgoing from Zulip, so
that it will hit a web endpoint that runs a third-party custom app.

Zulip will allow the custom app author, probably with the help of a
Zulip admin, to configure Zulip to send a subset of Zulip messages
to the author's web endpoint, and then the protocol for the
custom app will to read the HTTP request and
send some kind of HTTP response that optionally results in a
message being written to Zulip.  Meanwhile, the custom app can mutate
the "world" as it sees fit.


### Zulip-side support for reader apps

Even for app authors that have access to dedicated hardware,
there would be several advantages to running **Zulip Readers** under
the same umbrella as the core Zulip system.

- Your app will automatically inherit the uptime of the Zulip server itself (in
terms of hardware availability).
- There will be no network latency between the app and the server.
- Securing apps to have superuser permissions will be less problematic.
- Keeping your app in sync with Zulip upgrades could become more automatic.
- Allowing multiple users in your realm to run their own copies of personal-use bots
would be easier to administer.

The only problem with the above bullets is that we haven't built out any
of that infrastructure yet.

We do have pending [PR #1393](https://github.com/zulip/zulip/pull/1393), which
addresses some of the issues that might come up.

In order to run apps inside the Zulip server, we basically need to solve
the problems below.  (One assumption is that we don't run apps truly
in-process.)

- **Contributions**: We need a process for users to contribute code.
- **Configuration/Discovery**: We need Zulip to be able to find which
apps are allowed to run for a particular
deployment.  (The admin may choose to run only a subset of contributed
apps.)
- **Queuing**: We need to queue up events for readers, with some possible optimizations
to scan for alert words during the in-process part of the call.
- **Drivers**: We need a generic driver that can pull events off of a queue and
hand them off to our specific reader objects.
- **Nannying**: We need to launch readers with some kind of supervisord-like nannying.
- **Pausing**: We probably need a way to pause/stop readers without stopping the Zulip
main processes.  (At first this may just be part of solving the nanny problem.)
- **Identity**: We need to identify reader instances as specific Zulip
users (non-owned bot, human-owned bot, or human).
- **Superusers**: We may need some readers to have users with special privileges like being
auto-subscribed to all public streams.
- **Read-only**: We may need some readers at the other end of the spectrum to be
highly locked down, e.g. enforce that they truly only have read access
to Zulip messages.
- **UI**: We will want to provide some UI features that give admins and/or
regular users visibility into which server-side apps are running.
