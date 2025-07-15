# Self-hosted Zulip billing

This page describes how to manage your self-hosted plan, and answers some common
questions about plans and billing for self-hosted organizations. Please refer to
[Self-hosted Zulip plans and pricing](https://zulip.com/plans/#self-hosted) for plan
details.

The topics covered include:

* [Self-hosted plans overview](#self-hosted-plans-overview)
* [Logging in to manage billing](#log-in-to-billing-management)
* [Upgrading to a paid plan](#upgrade-to-a-paid-plan)
* [Managing billing](#manage-billing)
* [Canceling a paid plan](#cancel-paid-plan)
* [Applying for a free Community plan](#apply-for-community-plan)
* [Applying for a paid plan discount](#apply-for-a-paid-plan-discount)
* [Payment methods](#payment-methods)
* [License management options](#license-management-options)

If you have any questions not answered here, please don't hesitate to
reach out at [sales@zulip.com](mailto:sales@zulip.com).

## Self-hosted plans overview

Organizations that self-host Zulip can take advantage of the following plan
options:

- **Free**: Includes free access to Zulip's [Mobile Push Notification
  Service][push-notifications] for up to 10 users.

- **Basic**: Includes unlimited access to Zulip's [Mobile Push Notification
  Service][push-notifications] for organizations with more than 10 users.

- **Business**: Includes commercial support, in addition to push notifications
  access. Zulip's support team can answer questions about installation and
  upgrades, provide guidance in tricky situations, and help avoid painful
  complications before they happen. You can also get guidance on how best to use
  dozens of Zulip features and configuration options.

- **Enterprise**: If your organization requires hands-on support, such as
  real-time assistance during installation and upgrades, help with advanced
  deployment options, development of custom features or integrations, etc.,
  please contact [sales@zulip.com](mailto:sales@zulip.com) to discuss pricing.

- **Community**: This free plan includes unlimited push notifications access,
  and is available for many non-commercial organizations with more than 10 users
  (details [below](#free-community-plan)).

For full plan details, please take a look at [self-hosted Zulip plans and
pricing](https://zulip.com/plans/#self-hosted).

There is no option to combine multiple plans (e.g., Free and Basic) within a
single organization. Pricing is [based on](#license-management-options) the
number of non-deactivated users, not on which features each user is taking
advantage of. However, paid plan discounts are available in a variety of
situations; see [below](#paid-plan-discounts) for details.

### Organization plan or server plan?

You can purchase self-hosted plans for a Zulip organization, or for your entire
server.

If your server hosts a single Zulip organization, follow the
[instructions](#log-in-to-billing-management) for organization-level billing
(available on Zulip Server 8.0+). This will provide a more convenient plan
management experience.

If your server hosts multiple organizations, you can manage plans individually
for each organization, or purchase a single plan to cover your entire server.
Commercial support for any server-wide configurations requires upgrading the
organization with the largest number of users.

## Log in to billing management

Once you are logged in, you can [upgrade to a paid
plan](#upgrade-to-a-paid-plan), [manage billing](#manage-billing), [cancel a
paid plan](#cancel-paid-plan), or [apply for a free Community
plan](#apply-for-community-plan) or a [paid plan
discount](#apply-for-a-paid-plan-discount).

{start_tabs}

{tab|organization-billing}

!!! warn ""

    This feature is only available to organization [owners](/help/user-roles) and billing administrators.

1. Your Zulip server administrator should register the server with Zulip's
   Mobile Push Notification Service, following [these
   instructions](https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html).
   The Zulip Server 10.0+ installer includes a `--push-notifications` flag that
   automates this registration process.

1. Click on the **gear** (<i class="zulip-icon zulip-icon-gear"></i>) icon in
   the upper right corner of the web or desktop app.

1. Select <i class="zulip-icon zulip-icon-rocket"></i> **Plan management**.

1. *(first-time log in)* Enter the email address you want to use for plan
   management, and click **Continue**.

1. *(first-time log in)* In your email account, open the email you received
   (Subject: Confirm email for Zulip plan management), and click **Confirm and
   log in**.

1. *(first-time log in)* Enter your name, configure your email preferences, and
   accept the [Terms of Service](https://zulip.com/policies/terms).

1. Verify your information, and click **Continue**.

{tab|server-billing}

!!! tip ""

    A **server administrator** is anyone who sets up and manages your Zulip
    installation. A **billing administrator** is anyone responsible for managing
    your Zulip plan.

**Server administrator steps:**

1. Register the server with Zulip's Mobile Push Notification Service, following
   [these
   instructions](https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html).
   The Zulip Server 10.0+ installer includes a `--push-notifications` flag that
   automates this registration process.

1. Go to [https://selfhosting.zulip.com/serverlogin/](https://selfhosting.zulip.com/serverlogin/).

1. Fill out the requested server information, and click **Continue**.

1. Enter the email address of the billing contact for your organization,
   and click **Confirm email**.

**Billing administrator steps:**

1. In your email account, open the email you received
   (Subject: Log in to Zulip plan management), and click **Log in**.

1. Verify your information, and click **Continue**. If you are logging in for
   the first time, you will need to enter your name and accept the [Terms of
   Service](https://zulip.com/policies/terms).

{end_tabs}

## Upgrade to a paid plan

### Start a free trial

**New customers** are eligible for a free 30-day trial of the **Basic** plan.
An organization is considered to be a new customer if:

- It was not registered for Zulip's [Mobile Push Notification
  Service][push-notifications] prior to December 12, 2023, and

- It has never previously signed up for a self-hosted Zulip plan (Basic,
  Business, Community or Enterprise).

{start_tabs}

{tab|by-card}

{!self-hosted-billing-log-in-step.md!}

1. On the page listing Zulip's self-hosted plans, click the **Start
   30-day trial** button at the bottom of the **Basic** plan.

1. Click **Add card** to enter your payment details.

1. *(optional)* Update the billing details included on receipts so that
   they are different from the information entered for the payment method,
   e.g., in case you would prefer that the company's name be on receipts
   instead of the card holder's name.

1. Click **Start 30-day trial** to start your free trial.

!!! tip ""

    Once you start the trial, you can switch between monthly and annual
    billing on your organization's billing page. You can
    [cancel](#cancel-paid-plan) any time during your trial to avoid any charges.

{tab|by-invoice}

{!pay-by-invoice-warning.md!}

{!self-hosted-billing-log-in-step.md!}

1. On the page listing Zulip's self-hosted plans, click the **Start
   30-day trial** button at the bottom of the **Basic** plan.

1. Select **pay by invoice**.

1. Select your preferred option from the **Payment schedule** dropdown.

1. Select the **Number of licenses** you would like to purchase for your
   organization. You can adjust this number to update your initial invoice any
   time during your trial.

1. Click **Update billing information** to enter your billing details, which
   will be included on invoices and receipts.

1. Click **Start 30-day trial** to start your free trial.

{end_tabs}

### Upgrade directly to a paid plan

{start_tabs}

{tab|by-card}

{!self-hosted-billing-log-in-step.md!}

1. On the page listing Zulip's self-hosted plans, click the button at the bottom
   of the plan you would like to purchase.

{!plan-upgrade-steps.md!}

{tab|by-invoice}

{!pay-by-invoice-warning.md!}

{!self-hosted-billing-log-in-step.md!}

1. On the page listing Zulip's self-hosted plans, click the button at the bottom
   of the plan you would like to purchase.

{!pay-by-invoice-steps.md!}

{end_tabs}

## Manage billing

{!manage-billing-intro.md!}

### Manage billing

{start_tabs}

{!self-hosted-billing-log-in-step.md!}

{end_tabs}

### Configure who can manage plans and billing

{!configure-who-can-manage-plans.md!}

## Cancel paid plan

If you cancel your plan, your organization will be downgraded to the
**Free** plan at the end of the current billing period.

{start_tabs}

{!self-hosted-billing-log-in-step.md!}

1. At the bottom of the page, click **Cancel plan**.

1. Click **Downgrade** to confirm.

{end_tabs}

## Free Community plan

Zulip sponsors free plans for over 1000 worthy organizations. The following
types of organizations are generally eligible for the **Community** plan.

- Open-source projects, including projects with a small paid team.
- Research in an academic setting, such as research groups, cross-institutional
  collaborations, etc.
- Organizations operated by individual educators, such as a professor teaching
  one or more classes.
- Non-profits with no paid staff.
- Communities and personal organizations (clubs, groups of
  friends, volunteer groups, etc.).

Organizations that have up to 10 users, or do not require mobile push
notifications, will likely find the **Free** plan to be the most convenient
option. Larger organizations are encouraged to apply for the **Community**
plan, which includes unlimited push notifications and support for many Zulip
features.

If you aren't sure whether your organization qualifies, submitting a sponsorship
form describing your situation is a great starting point. Many organizations
that don't qualify for the **Community** plan can still receive [discounted paid
plan pricing](#paid-plan-discounts).

### Apply for Community plan

These instructions describe the **Community** plan application process for an
existing Zulip server. If you would like to inquire about eligibility prior to
setting up a self-hosted server, contact [sales@zulip.com](mailto:sales@zulip.com).

{start_tabs}

{!self-hosted-billing-log-in-step.md!}

1. On the page listing Zulip's self-hosted plans, scroll down to the
   **Sponsorship and discounts** area, and click **Apply here**.

1. Fill out the requested information, and click **Submit**. Your application
   will be reviewed for **Community** plan eligibility.

!!! tip ""

    Organizations that do not qualify for a **Community** plan may be offered a
    discount for the **Basic** plan.

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
teaching one or more classes) are generally eligible for [the Community
plan](#free-community-plan).

Departments and other institutions using Zulip with students are eligible for
discounted education pricing. Other educational uses (e.g., by teaching staff or
university IT) may qualify for [non-profit pricing](#non-profit-pricing).

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

Non-profits with no paid staff are eligible for [the Community
plan](#free-community-plan).

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
eligibility prior to setting up a self-hosted server, contact
[sales@zulip.com](mailto:sales@zulip.com).

{start_tabs}

{!self-hosted-billing-log-in-step.md!}

1. On the page listing Zulip's self-hosted plans, scroll down to the
   **Sponsorship and discounts** area, and click **Apply here**.

1. Select your preferred option from the **Plan** dropdown.

1. Fill out the requested information, and click **Submit**. Your application
   will be reviewed for discount eligibility.

{end_tabs}

## Payment methods

### What are my payment options?

{!payment-options.md!}

### International SWIFT transfers

{!international-wire-transfers.md!}

## License management options

### How does automatic license management work?

{!automatic-billing.md!}

### How does manual license management work?

With manual license management, you choose and pay for a fixed number of
licenses for your organization or server. [Deactivating a
user](/help/deactivate-or-reactivate-a-user) frees up their license for reuse.

If the number of active users exceeds the number of licenses you've purchased,
any paid services included in your plan will be paused until this is addressed.
For example, you will lose access to the [Mobile Push Notification
Service][push-notifications] until you have purchased more licenses or
deactivated enough users.

#### Manually update number of licenses

{start_tabs}

{!self-hosted-billing-log-in-step.md!}

{!manual-add-license-instructions.md!}

{end_tabs}

## How paid plans support the Zulip project

Zulip is proudly independent, with [no venture capital funding][sustainable-growth],
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
the [Mobile Push Notification Service][push-notifications] is provided free of
charge for organizations with up to 10 users.

You can self-manage your Zulip installation without signing up for a plan. Get
started with the [installation guide][production-install].

## Related articles

* [Trying out Zulip](/help/trying-out-zulip)
* [Zulip Cloud or self-hosting?](/help/zulip-cloud-or-self-hosting)
* [Migrating from other chat tools](/help/migrating-from-other-chat-tools)
* [Contact support](/help/contact-support)

[basic-metadata]: https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html#uploading-basic-metadata
[usage-statistics]: https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html#uploading-usage-statistics
[push-notifications]: https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html
[production-install]: https://zulip.readthedocs.io/en/stable/production/install.html
[sustainable-growth]: https://zulip.com/values/#building-a-sustainable-business-aligned-with-our-values
