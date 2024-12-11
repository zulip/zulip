# Moving to Zulip

Welcome to Zulip! This page will guide you through the process of transitioning
your organization to Zulip. It assumes that you have [completed your initial
evaluation](/help/trying-out-zulip) of Zulip, decided [whether to use Zulip
Cloud or self-host](/help/zulip-cloud-or-self-hosting), and are ready to
introduce Zulip to your organization.

The following steps are described in more detail below:

{start_tabs}

1. [Create your organization](#create-your-organization).

1. [Sign up for a plan](#sign-up-for-a-plan).

1. [Configure your organization](#configure-your-organization).

1. [Prepare users for the transition](#prepare-users-for-the-transition).

1. [Invite users to join](#invite-users-to-join).

1. [Update your guidelines](#update-your-guidelines).

{end_tabs}

Each organization is unique, but we hope these common practices will help you
think through the transition process in your own context.

## Create your organization

You can create a new Zulip Cloud organization in less than two minutes. Setting
up a self-hosted server will take a bit longer, but is easy to do with Zulip's
[robust
installer](https://zulip.readthedocs.io/en/stable/production/install.html).

Zulip has import tools for [Slack](/help/import-from-slack),
[Mattermost](/help/import-from-mattermost) and
[Rocket.Chat](/help/import-from-rocketchat). You can import your organization's
chat data, including message history, users, channels, and custom emoji. To
inquire about importing data from another product, [contact Zulip
support](/help/contact-support).

Data is imported into Zulip as a new organization, so the best time to import is
when your team is about to start using Zulip for day-to-day work. This may be
part of your evaluation process, or after you've made the decision to move to
Zulip.

{start_tabs}

{tab|new-organizations}

1. If you plan to self-host, [set up your Zulip
   server](https://zulip.readthedocs.io/en/stable/production/install.html). You
   can self-host Zulip directly on Ubuntu or Debian Linux, in
   [Docker](https://github.com/zulip/docker-zulip), or with prebuilt images for
   [Digital Ocean](https://marketplace.digitalocean.com/apps/zulip) and
   [Render](https://render.com/docs/deploy-zulip).

1. Create a Zulip organization [on Zulip Cloud](https://zulip.com/new/) or [on
   your self-hosted
   server](https://zulip.readthedocs.io/en/stable/production/install.html#step-3-create-a-zulip-organization-and-log-in).

{tab|imported-organizations}

1. If you plan to self-host, [set up your Zulip
   server](https://zulip.readthedocs.io/en/stable/production/install.html). You
   can self-host Zulip directly on Ubuntu or Debian Linux, in
   [Docker](https://github.com/zulip/docker-zulip), or with prebuilt images for
   [Digital Ocean](https://marketplace.digitalocean.com/apps/zulip) and
   [Render](https://render.com/docs/deploy-zulip).

1. To import data, follow the steps in the detailed import guides:

    * [Import from Slack](/help/import-from-slack)
    * [Import from Mattermost](/help/import-from-mattermost)
    * [Import from Rocket.Chat](/help/import-from-rocketchat)

{end_tabs}

## Sign up for a plan

If you require features that are not available on [Zulip Cloud
Free](https://zulip.com/plans/#cloud) or the [Zulip
Free](https://zulip.com/plans/#self-hosted) plan for self-hosted organizations,
you will need to upgrade your plan.

{start_tabs}

{tab|zulip-cloud}

1. Follow the
   [instructions](/help/zulip-cloud-billing#upgrade-to-a-zulip-cloud-standard-or-plus-plan)
   to upgrade to a Zulip Cloud Standard or Plus plan. If your organization may
   be
   [eligible](/help/zulip-cloud-billing#free-and-discounted-zulip-cloud-standard)
   for a free or discounted plan, you can [apply for
   sponsorship](/help/zulip-cloud-billing#apply-for-sponsorship).

{tab|self-hosting}

1. Follow the [instructions](/help/self-hosted-billing#upgrade-to-a-paid-plan)
   to upgrade to a Zulip Basic or Zulip Business plan. If your organization may
   be [eligible](/help/self-hosted-billing#free-community-plan) for a free or
   discounted plan, you can [apply for
   sponsorship](/help/self-hosted-billing#apply-for-community-plan). To inquire
   about Zulip Enterprise, please reach out to
   [sales@zulip.com](mailto:sales@zulip.com).

{end_tabs}

## Configure your organization

{start_tabs}

1. [Create your organization profile](/help/create-your-organization-profile),
   which is displayed on your organization's registration and login pages.

1. [Create user groups](/help/create-user-groups), which offer a flexible way to
   manage permissions.

1. Review [organization permissions](/help/manage-permissions), such as who
   can invite users, create channels, etc.

1. If your organization uses an issue tracker (e.g., GitHub, Salesforce,
   Zendesk, Jira, etc.), configure [linkifiers](/help/add-a-custom-linkifier) to
   automatically turn issue numbers (e.g., #2468) into links.

1. Set up [custom profile fields](/help/custom-profile-fields), which make it
   easy for users to share information, such as their pronouns, job title, or
   team.

1. Review [default user settings](/help/configure-default-new-user-settings),
   including language, [default visibility for email
   addresses](/help/configure-email-visibility), and notification preferences.

1. [Create channels](/help/create-channels), unless you've imported
   channels from another app. Zulip's [topics](/help/introduction-to-topics)
   give each conversation its own space, so one channel per team should be
   enough to get you started.

1. [Set up integrations](/help/set-up-integrations) so that your
   team can experience all their regular workflows inside the Zulip app. Zulip's
   [Slack-compatible incoming
   webhook](https://zulip.com/integrations/doc/slack_incoming) makes it easy to
   move your integrations when migrating an organization from Slack to Zulip.

{end_tabs}

## Prepare users for the transition

{start_tabs}

1. Plan how you will introduce users to Zulip. You may want to:

    - Share Zulip's [getting started guide](/help/getting-started-with-zulip).
    - Prepare a live demo / training session. Consider recording it for
     future use!

1. Inform users about the transition, including why you're moving to Zulip, the
   timeline, and what they'll need to do.

{end_tabs}

## Invite users to join

{!how-to-invite-users-to-join.md!}

## Update your guidelines

{start_tabs}

1. Update any links and login instructions to point to your Zulip organization.

1. Share basic instructions for getting started with Zulip. You can refer users
   to Zulip's [help center](/help), [getting started
   guide](/help/getting-started-with-zulip), and any onboarding content you've
   created.

1. Consider updating your organization's communication policies and best
   practice recommendations to take advantage of Zulip's organized
   conversations:

    - Many organizations find that with Zulip, there’s no longer a reason to use
      email for internal communications. You get the organization of an email
      [inbox](/help/inbox) together with all the features of a modern chat app,
      like instant delivery of messages, emoji reactions, typing notifications,
      @-mentions, and more.

    - Using Zulip, you can discuss complex topics and make decisions with input
      from all stakeholders, without the overhead of scheduling meeting. Are
      there standing meetings you might not need?

    - With conversations organized by topic, you can review prior discussions to
      understand past work, explanations, and decisions — your chat history
      becomes a knowledge base. Should it be standard practice to link to Zulip
      conversations from docs, issue trackers, etc. for additional context?

{end_tabs}

Congratulations on making the move! If you have any questions or feedback
throughout this process, please [reach out](/help/contact-support) to the Zulip
team.

## Related articles

* [Trying out Zulip](/help/trying-out-zulip)
* [Zulip Cloud or self-hosting?](/help/zulip-cloud-or-self-hosting)
* [Migrating from other chat tools](/help/migrating-from-other-chat-tools)
* [Getting started with Zulip](/help/getting-started-with-zulip)
