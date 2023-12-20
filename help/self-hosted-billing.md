# Self-hosted Zulip billing

This page describes how to manage your self-hosted plan, and answers some common
questions about plans and billing for self-hosted organizations. Please refer to
[Self-hosted Zulip plans and pricing](https://zulip.com/plans/#self-hosted) for plan
details.  If you have any questions not answered here, please don't hesitate to
reach out at [sales@zulip.com](mailto:sales@zulip.com).

## Business plan details and upgrades

The Business plan is appropriate for most business organizations. It includes
unlimited access to the Mobile Push Notification Service and commercial support
for dozens of features and integrations that help businesses take full advantage
of their Zulip implementation.

For businesses with up to 10 Zulip users, the Self-managed plan is a good
option, and includes free access to the Mobile Push Notification service. For
commercial support with your installation, sign up for the Business plan, with a
minimum purchase of 10 licenses.

If you organization requires hands-on support, such as real-time support during
installation and upgrades, support for advanced deployment options, custom
feature development or integrations, etc., should contact
[sales@zulip.com](mailto:sales@zulip.com) to discuss pricing.

Business plan discounts are available in a variety of situations; see
[below](#business-plan-discounts) for details.

### Upgrades for legacy customers

Any Zulip server that registered for Zulip's [Mobile Push Notification
Service](https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html)
prior to December 12, 2023 is considered to be a **legacy customer**. Legacy
customers can continue using the notification service for free (no action
required) until February 15, 2024.

To continue using the service after that date, organizations with more than 10
users must upgrade to the Business, Community or Enterprise plan. When you
upgrade to the Business plan, you can start the plan right away (if you‘d like
your technical support to start immediately), or schedule a February 15 start date.

#### Do I have to upgrade my server first?

While upgrading your Zulip server to version 8.0+ makes it more convenient to
manage your plan, you do not have to upgrade your Zulip installation in order to
sign up for a plan. **The same plans are offered for all Zulip versions.**

In addition to hundreds of other improvements, upgrading to Zulip Server 8.0+ lets
you:

- Easily log in to Zulip plan management, without an additional server
  authentication step.

- Separately manage plans for all the organizations on your server.

- Upload only the [basic
  metadata](https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html#uploading-basic-metadata)
  required for the service, without also [uploading usage
  statistics](https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html#uploading-usage-statistics).

If you upgrade your server after signing up for a plan, you will be able to
transfer your plan to an organization on your server. If your server has one
organization on it, this will happen automatically. Otherwise, contact
[support@zulip.com](mailto:support@zulip.com) for help.

#### Upgrading to Zulip Business

{!self-hosted-billing-multiple-organizations.md!}

{start_tabs}

{tab|v8}

{!self-hosted-billing-admin-only.md!}

{!self-hosted-log-in.md!}

1. You will be logged in to Zulip's [Plans and pricing
   page](https://zulip.com/plans/). Under the **Business** pricing plan on the
   **Self-hosted** tab, click **Upgrade to Business**.

1. Select your preferred option from the **Payment schedule** dropdown.

1. Under **Plan start date**, select **February 15, 2024** or **Today**.

1. Click **Add card** to enter your payment details.

1. Click **Purchase Zulip Business** to upgrade immediately, or **Schedule
   upgrade to Zulip Business** to schedule an upgrade for February 15.

!!! warn ""

    If your server hosts more than one organization, commercial
    support for server-wide configurations requires upgrading the
    organization with the largest number of users.

{tab|older-versions}

{!legacy-log-in-intro.md!}

{!legacy-log-in.md!}

1. Select your preferred option from the **Payment schedule** dropdown.

1. Under **Plan start date**, select **February 15, 2024** or **Today**.

1. Click **Add card** to enter your payment details.

1. Click **Purchase Zulip Business** to upgrade immediately, or **Schedule
   upgrade to Zulip Business** to schedule an upgrade for February 15.

{end_tabs}

### Upgrades for new customers

**New customers** are eligible for a free 30-day trial of Zulip Business. An
organization is considered to be a new customer if:

- It was not registered for Zulip's [Mobile Push Notification
  Service](https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html)
  prior to December 12, 2023, and
- It has never previously signed up for a self-hosted Zulip plan (Business,
  Community or Enterprise).

{!self-hosted-billing-multiple-organizations.md!}

{start_tabs}

{tab|v8}

{!register-server.md!}

{!self-hosted-log-in.md!}

1. Under the **Business** pricing plan on the **Self-hosted** tab, click
   **Start 30-day trial**.

2. Click **Add card** to enter your payment details.

3. Click **Start 30-day trial** to start your free trial.

!!! tip ""

    Once you start the trial, you can switch between monthly and annual billing
    on your organization's billing page.

!!! warn ""

    If your server hosts more than one organization, commercial
    support for server-wide configurations requires upgrading the
    organization with the largest number of users.

{tab|older-versions}

{!legacy-log-in-intro.md!}

{!register-server-legacy.md!}

{!legacy-log-in.md!}

1. Under the **Business** pricing plan on the **Self-hosted** tab, click
   **Start 30-day trial**.

1. Click **Add card** to enter your payment details.

1. Click **Start 30-day trial** to start your free trial.

!!! tip ""

    Once you start the trial, you can switch between monthly and annual billing
    on your organization's billing page.

{end_tabs}

## Manage billing

{!self-hosted-billing-multiple-organizations.md!}

{start_tabs}

{tab|v8}

{!self-hosted-log-in.md!}

{tab|older-versions}

{!legacy-log-in-intro.md!}

{!legacy-log-in.md!}

{end_tabs}

## Cancel paid plan

{!self-hosted-billing-multiple-organizations.md!}

If you cancel your plan, your organization will be downgraded to the
**Self-managed** plan at the end of the current billing period.

{start_tabs}

{tab|v8}

{!self-hosted-log-in.md!}

1. At the bottom of the page, click **Cancel plan**.

2. Click **Downgrade** to confirm.

{tab|older-versions}

{!legacy-log-in-intro.md!}

{!legacy-log-in.md!}

1. At the bottom of the page, click **Cancel plan**.

1. Click **Downgrade** to confirm.

{end_tabs}

## Free Community plan

Zulip sponsors free plans for over 1000 worthy organizations. The following
types of organizations are generally eligible for the free Community plan.

- Open-source projects, including projects with a small paid team.
- Research organizations, such as research groups, cross-institutional
  collaborations, etc.
- Education and non-profit organizations with up to 100 users.
- Communities and personal organizations (clubs, groups of
  friends, volunteer groups, etc.).

Organizations that have up to 10 users, or do not require mobile push
notifications, will likely find the Self-managed plan to be the most convenient
option. Larger organizations are encouraged to apply for the free Community
plan, which includes unlimited push notifications and support for many Zulip
features.

If you aren't sure whether your organization qualifies, submitting a sponsorship
form describing your situation is a great starting point. Many organizations
that don't qualify for the Community plan can still receive discounted Business
plan pricing.

### Apply for Community plan

These instructions describe the Community plan application process for an
existing Zulip server. If you would like to inquire about Community plan
eligibility prior to setting up a server, contact
[sales@zulip.com](mailto:sales@zulip.com).

!!! tip ""

    Organizations that do not qualify for a Community plan may be offered a
    discount on the Business plan.

{start_tabs}

{tab|v8}

{!register-server.md!}

{!self-hosted-log-in.md!}

1. Under the **Community** pricing plan on the **Self-hosted** tab, click
   **Apply to upgrade**.

1. Fill out the requested information, and click **Submit**. Your application
   will be reviewed for Community plan eligibility.

{tab|older-versions}

{!legacy-log-in-intro.md!}

{!register-server-legacy.md!}

{!legacy-log-in.md!}

1. Under the **Community** pricing plan on the **Self-hosted** tab, click
   **Apply to upgrade**.

1. Fill out the requested information, and click **Submit**. Your application
   will be reviewed for Community plan eligibility.

!!! tip ""

    Organizations that do not qualify for a Community plan may be offered a
    discount on the Business plan.

{end_tabs}

## Business plan discounts

The following types of organizations are generally eligible for significant
discounts on the Zulip Business plan. You can also contact
[sales@zulip.com](mailto:sales@zulip.com) to discuss bulk discount pricing for a
large organization.

- **Education pricing** is available with a minimum purchase of 100 licenses.
  Organizations with up to 100 users are eligible for free Community plan
  sponsorship.

    - **For-profit education pricing**: $1 per user per month with annual billing
      ($1.20/month billed monthly).

    - **Non-profit education pricing**: $0.67 per user per month with annual billing
      ($0.80/month billed monthly). The non-profit discount applies to
      online purchases only (no additional legal agreements) for use at registered
      non-profit institutions (e.g. colleges and universities).

- **Non-profit** discounts of 85+% are available with a minimum purchase of 100
  licenses. Organizations with up to 100 users are eligible for free Community plan
  sponsorship.

- Discounts are available for organizations based in the **developing world**.

- Any organization where many users are **not paid staff** is likely eligible for a discount.

### Apply for Business plan discount

These instructions describe the Business plan discount application process for an
existing Zulip server. If you would like to inquire about Business plan discount
eligibility prior to setting up a server, contact
[sales@zulip.com](mailto:sales@zulip.com).

{start_tabs}

{tab|v8}

{!register-server.md!}

{!self-hosted-log-in.md!}

1. Under **Sponsorship and discounts** on the **Self-hosted** tab, click
   **Request sponsorship**.

1. Under **Plan**, select **Business**.

1. Fill out the requested information, and click **Submit**. Your application
   will be reviewed for discount eligibility.

{tab|older-versions}

{!legacy-log-in-intro.md!}

{!register-server-legacy.md!}

{!legacy-log-in.md!}

1. Under **Sponsorship and discounts** on the **Self-hosted** tab, click
   **Request sponsorship**.

1. Under **Plan**, select **Business**.

1. Fill out the requested information, and click **Submit**. Your application
   will be reviewed for discount eligibility.

{end_tabs}

## Payment methods

### Can I pay by credit card and/or invoice?

You can always use a credit card to pay. If you would like to pay by invoice,
you will need to sign up for an annual plan.

### What is the difference between automatic and manual billing?

{!manual-billing-intro.md!}

#### Manually manage licenses

{start_tabs}

{tab|v8}

{!self-hosted-log-in.md!}

1. Modify **Number of licenses for current billing period** or **Number of
   licenses for next billing period**, and click **Update**.

!!! tip ""

    You can only increase the number of licenses for the current billing period.

{tab|older-versions}

{!legacy-log-in-intro.md!}

{!legacy-log-in.md!}

1. Modify **Number of licenses for current billing period** or **Number of
   licenses for next billing period**, and click **Update**.

!!! tip ""

    You can only increase the number of licenses for the current billing period.

{end_tabs}

## Self-managed installations

Zulip is 100% open-source. Organizations that do not require support with their
installation can always use Zulip for free with no limitations. Additionally,
the [Mobile Push Notification
Service](https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html)
is provided free of charge for organizations with up to 10 users.

You can self-manage your Zulip installation without signing up for a plan. Get
started with the [installation
guide](https://zulip.readthedocs.io/en/stable/production/install.html).

## Related articles

* [Trying out Zulip](/help/trying-out-zulip)
* [Zulip Cloud or self-hosting?](/help/zulip-cloud-or-self-hosting)
* [Migrating from other chat tools](/help/migrating-from-other-chat-tools)
* [Contact support](/help/contact-support)
