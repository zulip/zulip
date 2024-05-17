# Self-hosted Zulip billing

This page describes how to manage your self-hosted plan, and answers some common
questions about plans and billing for self-hosted organizations. Please refer to
[Self-hosted Zulip plans and pricing](https://zulip.com/plans/#self-hosted) for plan
details.  If you have any questions not answered here, please don't hesitate to
reach out at [sales@zulip.com](mailto:sales@zulip.com).

## Paid plan details and upgrades

For businesses with up to 10 Zulip users, the Free plan is a good option, and
includes free access to the Mobile Push Notification Service.

For businesses with more than 10 Zulip users, both the Basic and Business plans
include unlimited access to the Mobile Push Notification Service.

The Business plan also includes commercial support for dozens of features and
[integrations](/help/integrations-overview) that help businesses take full advantage of their Zulip
implementation. The minimum purchase is 25 licenses.

If your organization requires hands-on support, such as real-time support during
installation and upgrades, support for advanced deployment options, custom
feature development or integrations, etc., should contact
[sales@zulip.com](mailto:sales@zulip.com) to discuss pricing.

Paid plan discounts are available in a variety of situations; see
[below](#paid-plan-discounts) for details.

## Upgrade to a paid plan

### Start a free trial

**New customers** are eligible for a free 30-day trial of Zulip Basic. An
organization is considered to be a new customer if:

- It was not registered for Zulip's [Mobile Push Notification
  Service](https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html)
  prior to December 12, 2023, and
- It has never previously signed up for a self-hosted Zulip plan (Basic, Business,
  Community or Enterprise).

{start_tabs}

{tab|v8}

{!register-server.md!}

{!self-hosted-log-in.md!}

1. On the page listing Zulip's self-hosted plans, click the **Start 30-day
   trial** button at the bottom of the **Basic** plan.

1. Click **Add card** to enter your payment details.

1. Click **Start 30-day trial** to start your free trial.

!!! tip ""

    Once you start the trial, you can switch between monthly and annual billing
    on your organization's billing page.

{tab|all-versions}

{!legacy-log-in-intro.md!}

{!register-server-legacy.md!}

{!legacy-log-in.md!}

1. On the page listing Zulip's self-hosted plans, click the **Start 30-day
   trial** button at the bottom of the **Basic** plan.

1. Click **Add card** to enter your payment details.

1. Click **Start 30-day trial** to start your free trial.

!!! tip ""

    Once you start the trial, you can switch between monthly and annual billing
    on your organization's billing page.

{end_tabs}

### Upgrade directly to a paid plan

{!self-hosted-billing-multiple-organizations.md!}

{start_tabs}

{tab|v8}

{!self-hosted-billing-admin-only.md!}

{!self-hosted-log-in.md!}

1. On the page listing Zulip's self-hosted plans, click the button at the bottom
   of the plan you would like to purchase.

{!plan-upgrade-steps.md!}

!!! warn ""

    If your server hosts more than one organization, commercial
    support for server-wide configurations requires upgrading the
    organization with the largest number of users.

{tab|all-versions}

{!legacy-log-in-intro.md!}

{!legacy-log-in.md!}

{!plan-upgrade-steps.md!}

{end_tabs}

### Do I have to upgrade my server first?

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

## Manage billing

{!self-hosted-billing-multiple-organizations.md!}

{start_tabs}

{tab|v8}

{!self-hosted-log-in.md!}

{tab|all-versions}

{!legacy-log-in-intro.md!}

{!legacy-log-in.md!}

{end_tabs}

## Cancel paid plan

{!self-hosted-billing-multiple-organizations.md!}

If you cancel your plan, your organization will be downgraded to the
**Free** plan at the end of the current billing period.

{start_tabs}

{tab|v8}

{!self-hosted-log-in.md!}

1. At the bottom of the page, click **Cancel plan**.

2. Click **Downgrade** to confirm.

{tab|all-versions}

{!legacy-log-in-intro.md!}

{!legacy-log-in.md!}

1. At the bottom of the page, click **Cancel plan**.

1. Click **Downgrade** to confirm.

{end_tabs}

## Free Community plan

Zulip sponsors free plans for over 1000 worthy organizations. The following
types of organizations are generally eligible for the free Community plan.

- Open-source projects, including projects with a small paid team.
- Research in an academic setting, such as research groups, cross-institutional
  collaborations, etc.
- Organizations operated by individual educators, such as a professor teaching
  one or more classes.
- Non-profits with no paid staff.
- Communities and personal organizations (clubs, groups of
  friends, volunteer groups, etc.).

Organizations that have up to 10 users, or do not require mobile push
notifications, will likely find the Free plan to be the most convenient
option. Larger organizations are encouraged to apply for the free Community
plan, which includes unlimited push notifications and support for many Zulip
features.

If you aren't sure whether your organization qualifies, submitting a sponsorship
form describing your situation is a great starting point. Many organizations
that don't qualify for the Community plan can still receive [discounted paid
plan pricing](#paid-plan-discounts).

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

1. On the page listing Zulip's self-hosted plans, scroll down to the
   **Sponsorship and discounts** area, and click **Apply here**.

1. Fill out the requested information, and click **Submit**. Your application
   will be reviewed for Community plan eligibility.

{tab|all-versions}

{!legacy-log-in-intro.md!}

{!register-server-legacy.md!}

{!legacy-log-in.md!}

1. On the page listing Zulip's self-hosted plans, scroll down to the
   **Sponsorship and discounts** area, and click **Apply here**.

1. Fill out the requested information, and click **Submit**. Your application
   will be reviewed for Community plan eligibility.

!!! tip ""

    Organizations that do not qualify for a Community plan may be offered a
    discount on the Business plan.

{end_tabs}

## Paid plan discounts

The following types of organizations are generally eligible for significant
discounts on paid plans. You can also contact
[sales@zulip.com](mailto:sales@zulip.com) to discuss bulk discount pricing for a
large organization.

- [Education organizations](#education-pricing) and [non-profit
  organizations](#non-profit-pricing).

- Discounts are available for organizations based in the **developing world**.

- Any organization where many users are **not paid staff** is likely eligible
  for a discount.

If there are any circumstances that make regular pricing unaffordable for your
organization, contact [sales@zulip.com](mailto:sales@zulip.com) to discuss your
situation.

### Education pricing

Organizations operated by individual educators (for example, a professor
teaching one or more classes) are generally eligible for a free
Community plan.

Departments and other institutions using Zulip are eligible for discounted
education pricing.

- **For-profit education pricing**:
    - **Basic plan**: $0.50 per user per month
    - **Business plan**: $1 per user per month with annual billing
    ($1.20/month billed monthly) with a minimum purchase of 100 licenses.

- **Non-profit education pricing**: The non-profit discount applies to
  online purchases only (no additional legal agreements) for use at registered
  non-profit institutions (e.g., colleges and universities).
    - **Basic plan**: $0.35 per user per month
    - **Business plan**: $0.67 per user per month with annual billing
      ($0.80/month billed monthly) with a minimum purchase of 100 licenses.

### Non-profit pricing

Non-profits with no paid staff are eligible for the free Community plan.

For non-profits with paid staff, volunteers and other unpaid participants in
your community are eligible for free Zulip accounts. Additionally, discounts are
available for paid staff accounts. Contact
[sales@zulip.com](mailto:sales@zulip.com) to arrange discounted pricing for your
organization.

### Guest user discounts

There is no automatic discount for guest users. However, organizations with a
large number of guest users are very likely to be eligible for a discount. If
this is your situation, please apply for a discount or email
[sales@zulip.com](mailto:sales@zulip.com).

### Duplicate accounts

Some servers host multiple organizations, with some individuals having accounts in
several of these organizations. If you have this setup, the ability to
[configure whether guests can see other
users](/help/guest-users#configure-whether-guests-can-see-all-other-users)
(introduced in Zulip 8.0) may allow you to consolidate into a single Zulip
organization.

If you want to maintain a multi-organization setup with duplicate accounts, you
may contact [sales@zulip.com](mailto:sales@zulip.com) to arrange a discounted rate.

### Apply for a paid plan discount

These instructions describe the paid plan discount application process for an
existing Zulip server. If you would like to inquire about paid plan discount
eligibility prior to setting up a server, contact
[sales@zulip.com](mailto:sales@zulip.com).

{start_tabs}

{tab|v8}

{!register-server.md!}

{!self-hosted-log-in.md!}

1. On the page listing Zulip's self-hosted plans, scroll down to the
   **Sponsorship and discounts** area, and click **Apply here**.

1. Select your preferred option from the **Plan** dropdown.

1. Fill out the requested information, and click **Submit**. Your application
   will be reviewed for discount eligibility.

{tab|all-versions}

{!legacy-log-in-intro.md!}

{!register-server-legacy.md!}

{!legacy-log-in.md!}

1. On the page listing Zulip's self-hosted plans, scroll down to the
   **Sponsorship and discounts** area, and click **Apply here**.

1. Select your preferred option from the **Plan** dropdown.

1. Fill out the requested information, and click **Submit**. Your application
   will be reviewed for discount eligibility.

{end_tabs}

## Payment methods

### Can I pay by credit card and/or invoice?

You can always use a credit card to pay. If you would like to pay by invoice,
you will need to sign up for an annual plan.

### How does automatic billing work?

{!automatic-billing.md!}

### How does manual billing work?

{!manual-billing-intro.md!}

#### Manually manage licenses

{start_tabs}

{tab|v8}

{!self-hosted-log-in.md!}

1. Modify **Number of licenses for current billing period** or **Number of
   licenses for next billing period**, and click **Update**.

!!! tip ""

    You can only increase the number of licenses for the current billing period.

{tab|all-versions}

{!legacy-log-in-intro.md!}

{!legacy-log-in.md!}

1. Modify **Number of licenses for current billing period** or **Number of
   licenses for next billing period**, and click **Update**.

!!! tip ""

    You can only increase the number of licenses for the current billing period.

{end_tabs}

## How paid plans support the Zulip project

Zulip is proudly independent, with [no venture capital
funding](https://zulip.com/values/#building-a-sustainable-business-aligned-with-our-values),
which means that revenue strongly impacts the pace of Zulip’s development. Paid
plans for self-hosted customers help fund improvements in Zulip's self-hosting
experience, and overall product development. Zulip needs the support of
businesses that self-host Zulip in order to thrive as an independent, [100%
open-source](https://github.com/zulip/zulip#readme) project.

You can also learn about [other ways](/help/support-zulip-project) to support
the Zulip project.

## Self-hosting Zulip for free

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
