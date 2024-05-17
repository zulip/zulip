# Setting up Zulip for a class

Welcome to Zulip! This page will guide you through setting everything
up for [teaching with Zulip](https://zulip.com/for/education/). If you are using Zulip
for a different purpose, we recommend checking out the [Setting up
your organization][setting-up] guide instead.

If you are a student, or if your Zulip organization is already set up,
you can proceed to the [Using Zulip for a
class](/help/using-zulip-for-a-class) guide.

[getting-started]: /help/getting-started-with-zulip
[setting-up]: /help/getting-your-organization-started-with-zulip

If you encounter any problems as you're getting started, please drop
by our [friendly development community](/development-community/) and let
us know!

## Trying out Zulip

You can start by reading about [Zulip for Education](https://zulip.com/for/education/),
and how Zulip can become the communication hub for your class. Zulip
is the only [modern team chat app](/features/) that is
[ideal](/why-zulip/) for both live and asynchronous
conversations. Post lecture notes and announcements, answer students’
questions, and coordinate with teaching staff all in one place.

We also highly recommend trying Zulip for yourself! You can:

* [Create a Zulip Cloud organization](/new/) for free with just a few
  clicks.
* [Join the Zulip development community](/development-community/) to see
  Zulip in action. Feel free to introduce yourself and ask questions!


## Choosing between Zulip Cloud and self-hosting

Whether [signing up for Zulip Cloud](/new/) or [self-hosting
Zulip][install-self-hosted] is the right choice for you depends on your needs.

If you aren’t sure what you need, our high quality export and import
tools ([cloud][export-cloud], [self-hosted][export-self-hosted])
ensure you can always move from our hosting to yours (and back).

[install-self-hosted]: https://zulip.readthedocs.io/en/stable/production/install.html
[export-cloud]: /help/export-your-organization
[export-self-hosted]: https://zulip.readthedocs.io/en/stable/production/export-and-import.html

### Advantages of Zulip Cloud

* Simple managed solution, with no setup or maintenance
  overhead. [Sign up](/new/) with just a few clicks.
* Always updated to the latest version of Zulip.
* Anyone can [start with Zulip Cloud Free](/new/), which works well for a typical class.
* For large classes and departments, we offer [special Zulip for
  Education pricing](https://zulip.com/for/education/#feature-pricing), with the same
  features as Zulip Cloud Standard. You can always get started with
  Zulip Cloud Free, and upgrade down the line if needed.

### Advantages of self-hosting Zulip

* Zulip is [100% open-source software](https://github.com/zulip), with
  no "open core" catch.
* We work hard to make it easy to [set up][install-zulip],
  [back up][back-up-zulip], and [maintain][maintain-zulip] a self-hosted
  Zulip installation.
* Retain full control over your data. If cloud hosting is not an
  option due to stringent data and privacy requirements (e.g. in the
  European Union), self-hosting is the option for you.
* Customize Zulip for all your needs.

[install-zulip]: https://zulip.readthedocs.io/en/stable/production/install.html
[back-up-zulip]: https://zulip.readthedocs.io/en/stable/production/export-and-import.html#backups
[maintain-zulip]: https://zulip.readthedocs.io/en/stable/production/upgrade.html


## Do I need a separate Zulip organization for each class?
There are a few ways to set up Zulip, and different ones may be convenient for your needs:


* If your **school or department already has a Zulip organization**,
  you will probably find it easiest to just add your class to
  it. Advantages:
    - Students and staff can use a single Zulip account for all classes.
    - You can create department-wide channels, e.g. for announcing talks or other events.
    - You don’t need to set up a separate server if you’re self-hosting Zulip.

* You can **set up a separate Zulip organization for each class**
  you’re teaching. Advantages:
    - This makes it simple to manage permissions. e.g. if you want to
      make sure TAs from one class cannot moderate discussion from a
      different class.
    - Students can’t see who is in channels for other classes.
    - You can easily switch between multiple Zulip organizations in
      the [Zulip desktop apps](/apps/).


* You can **use a single Zulip organization for several classes**
  you’re teaching, perhaps re-purposing a Zulip organization from a
  prior term. Advantages:
    - Information from your classes is all in one place, e.g. if you
      want to re-post a response to a question that was also asked
      last time you taught the class.

If you change your mind down the line, you can rename your Zulip
organization by sending a request to
[support@zulip.com](mailto:support@zulip.com).

## Create your organization profile

The information in your organization profile is displayed on the
registration and login page for your organization, and in the Zulip app.

### Edit organization profile

{!edit-organization-profile.md!}

### Add a wide logo

{!add-a-wide-logo.md!}

## Customize organization settings

{!review-organization-settings-instructions.md!}

A few settings to highlight:

* If your class uses a programming language, set the [default
  language for code blocks][default-code-block-language]. Also
  consider setting up [code playgrounds][code-playgrounds].

* If your class uses code repositories, [set up
  linkifiers](/help/add-a-custom-linkifier) to make it easy to link to
  issues (e.g. just by typing #1234 for issue 1234).

* [Add custom emoji](/help/custom-emoji) that your class will enjoy.

[default-code-block-language]: /help/code-blocks#default-code-block-language
[code-playgrounds]: /help/code-blocks#code-playgrounds

### Roles and permissions

Zulip offers [several levels of permissions based on user
roles](/help/roles-and-permissions). Here are some recommendations for
how to assign roles and permissions for a class.

#### Recommended roles and permissions for a single-class Zulip organization

| Who                                 | Role                                           |
| ----------------------------------- | ---------------------------------------------- |
| Lead instructor, IT                 | Owner (also has all Administrator permissions) |
| Other instructors, head TA          | Administrator                                  |
| Teaching assistants, lab assistants | Moderator                                      |
| Students                            | Member                                         |

##### Settings

!!! warn ""
     These are the default permissions for new **Education
     (non-profit)** and **Education (for-profit)** organizations.

- Set [who can invite new users](/help/restrict-account-creation#change-who-can-send-invitations).
  (Recommended: Admins)
- Set [who can access user email addresses](/help/configure-email-visibility).
  (Recommended: Admins only)
- Set [who can create channels](/help/configure-who-can-create-channels).
  (Recommended: Admins for public channels; Admins, moderators and members for private channels)
- Set [who can add users to channels](/help/configure-who-can-invite-to-channels).
  (Recommended: Admins and moderators)
- Set [who can edit the topic of any message](/help/restrict-moving-messages).
  (Recommended: (default) Members for small classes;
  Admins and moderators for large classes)
- Set [who can move messages between channels][move-between-channels].
  (Recommended: Admins and moderators)
- Set [who can create and manage user groups][user-group-permissions].
  (Recommended: Admins and moderators)

[user-group-permissions]: /help/manage-user-groups#configure-who-can-create-and-manage-user-groups
[move-between-channels]: /help/restrict-moving-messages#configure-who-can-move-messages-to-another-channel

#### Recommended roles and permissions for a department

| Who                                           | Role                                           |
| --------------------------------------------- | ---------------------------------------------- |
| IT                                            | Owner (also has all Administrator permissions) |
| IT, department leadership                     | Administrator                                  |
| Professors, Lecturers, head TAs               | Moderator                                      |
| Teaching assistants, lab assistants, students | Member                                         |

##### Settings

- Set [who can invite new users](/help/restrict-account-creation#change-who-can-send-invitations).
  (Recommended: Admins and moderators)
- Set [who can access user email addresses](/help/configure-email-visibility).
  (Recommended: Admins only)
- Set [who can create channels](/help/configure-who-can-create-channels).
  (Recommended: Admins and moderators for public channels;
   Admins, moderators and members for private channels)
- Set [who can add users to channels](/help/configure-who-can-invite-to-channels).
  (Recommended: Admins and moderators)
- Set [who can edit the topic of any message](/help/restrict-moving-messages).
  (Recommended: Admins and moderators)
- Set [who can move messages between channels][move-between-channels].
  (Recommended: Admins and moderators)
- Set [who can create and manage user groups][user-group-permissions].
  (Recommended: Admins and moderators)

## Create channels

{!create-channels-intro.md!}

### How to create a channel

{start_tabs}

{relative|channel|all}

1. Click **Create channel** on the right.

1. Fill out the requested info, and click **Create**.

{end_tabs}

For more details about channel settings, see [Create a
channel](/help/create-a-channel#channel-options).

### Tips for creating channels

For most classes, the following channels are recommended:

- **#announcements**: For general announcements about the class. When
  creating this channel, [restrict posting
  permissions](/help/channel-posting-policy) so that only course staff
  ([administrators and moderators](/help/roles-and-permissions)) are
  allowed to post.
- **#staff (private)**: For discussions among course staff.
- **#general**: For random topics, e.g. students forming study groups.
- A channel for each **lecture** or **unit**, e.g. “Lecture 1: Course
  intro” or “Unit 3: Sorting algorithms”.
- A channel for each **section**/**tutorial group** (e.g. “Section 1”)


!!! tip ""

    You can start by creating channels for just the first few
    lectures/units at this point. When you create a new channel,
    you will be able to copy channel membership from existing channels.

A few notes:

- Small classes may need just one discussion channel for all lectures.
- If you are [using a single Zulip organization][separate-orgs] for
  more than one class, all channel names should be prefixed with the
  name of the class, e.g. “CS101 > Lecture 1: Course intro”.

[separate-orgs]: /help/setting-up-zulip-for-a-class#do-i-need-a-separate-zulip-organization-for-each-class

## Customize settings for new users

{!customize-settings-for-new-users.md!}

!!! tip ""

    If using your Zulip organization for a single class, set default
    channels for new users to include **#announcements**, **#general**,
    and all lecture/unit channels.

## Invite users to join

!!! tip ""

    Before inviting users, you may want to [delete any test
    messages][delete-message] or [topics](/help/delete-a-topic).

[delete-message]: /help/delete-a-message#delete-a-message-completely

### How to invite users to join

To simplify subscription management, be sure to set the channels
students and staff should be added to when you create the
invitations. You may choose to send invitations to course staff
separately, so that they can immediately be added to private channels
for your class.

{!how-to-invite-users-to-join.md!}

To get everyone off to a good start, you may wish to share the guide
to [Getting started with Zulip][getting-started] and the guide to
[Using Zulip for a class](/help/using-zulip-for-a-class).

!!! tip ""

    If you create new channels later on, you can add users
    [by group][create-user-groups] or copy membership from another
    channel (e.g. from Lecture 5 to Lecture 6).

[create-user-groups]: /help/setting-up-zulip-for-a-class#create-user-groups

## Create user groups

User groups allow you to [mention](/help/mention-a-user-or-group)
multiple users at once,
[notifying](/help/dm-mention-alert-notifications) them about a
message. For example, you may find it useful to set up the following
user groups:

- @staff
- @TAs
- @graders
- @students
- @section1, @section2, etc.

### How to create a user group

{!how-to-create-a-user-group.md!}

## Set up integrations

Zulip integrates directly with dozens of products, and with hundreds
more through [Zapier](/integrations/doc/zapier) and
[IFTTT](/integrations/doc/ifttt).  Popular Zulip integrations include
[GitHub](/integrations/doc/github) and
[Twitter](/integrations/doc/twitter). The [integrations
page](/integrations/) has instructions for integrating with each
product.

## Cleaning up at the end of a class

If you plan to use the same Zulip organization in future terms (either
for your own classes or for your department), you will likely want to:

- Rename all channels to indicate the class and term in which they were used, e.g.:
    - **#announcements** → **#FA21 - CS101 - announcements**
    - **#CS101 > Lecture 1: Course intro** → **#FA21 - CS101 > Lecture 1: Course
      intro**
- If you do *not* want students from future classes to see messages
  from the prior term (e.g. because you posted homework solutions),
  [make all the channels from the class private][make-private]. You’ll
  be able to find and reuse content yourself, and [invite course
  staff][add-to-channel] to these private channels as needed.
- You may choose to [deactivate students’ Zulip
  accounts][deactivate-user] when the class is over.
- [Unpin channels](/help/pin-a-channel) from the class from your
  personal view.

If you do not plan to reuse the Zulip organization, you can instead:

* [Export the organization](/help/export-your-organization) or [generate a static
HTML archive](https://github.com/zulip/zulip-archive) to archive the information.
* [Deactivate the organization](/help/deactivate-your-organization).

## Further reading

* [Using Zulip for a class](/help/using-zulip-for-a-class)
* [Getting started with Zulip](/help/getting-started-with-zulip)
* [Introduction to topics](/help/introduction-to-topics)
* [Moderating open organizations](/help/moderating-open-organizations)

[make-private]: /help/change-the-privacy-of-a-channel
[add-to-channel]: /help/add-or-remove-users-from-a-channel
[deactivate-user]: /help/deactivate-or-reactivate-a-user#deactivate-a-user
