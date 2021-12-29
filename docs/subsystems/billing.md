# Billing (Development)

This section deals with developing and testing the billing system.

## Common setup

- Create a Stripe account
  - Make sure that the country of your Stripe account is set to USA when
    you create the account.
  - You might need to use a VPN for this.
- Ensure that the [API version](https://stripe.com/docs/api/versioning) of
  your Stripe account is same as `STRIPE_API_VERSION` defined in
  `corporate/lib/stripe.py`. You can upgrade to a higher version from
  the Stripe dashboard.
- Set the private API key.
  - Go to <https://dashboard.stripe.com/account/apikeys>
  - Add `stripe_secret_key` to `zproject/dev-secrets.conf`.

## Manual testing

Manual testing involves testing the various flows like upgrade, card change,
etc. through the browser. This is the bare minimum testing that you need to
do when you review a billing PR or when you are working on adding a new
feature to billing.

### Setup

Apart from the common setup mentioned above, you also need to setup your
development environment to receive webhook events from Stripe.

- Install the Stripe CLI locally by following the instructions
  [here](https://stripe.com/docs/webhooks/test).
- Login to Stripe CLI using the command `stripe login`.
- You can get Stripe CLI to forward all Stripe webhook events to our local
  webhook endpoint using the following command:
  `stripe listen --forward-to http://localhost:9991/stripe/webhook/`
- Wait for the `stripe listen` command in the previous step to output the
  webhook signing secret.
  - The signing secret would be used by our billing system to verify that
    the events received by our webhook endpoint are sent by Stripe and not
    by an intruder. In production, there is no Stripe CLI, so the step for
    configuring this is a bit different. See Stripe's documentation on
    [taking webhooks live](https://stripe.com/docs/webhooks/go-live) for
    more details.
- Copy the webhook signing secret and set it as `stripe_webhook_endpoint_secret`
  in `zproject/dev-secrets.conf`.
- Your development environment is now all set to receive webhook events from
  Stripe.

### Test card numbers

Stripe provides various card numbers to test for specific responses from Stripe.
The most commonly used ones are mentioned in below wherever appropriate. The full
list is available [here](https://stripe.com/docs/testing#cards).

### Flows to test

There are various flows that you can test manually from the browser. Here are
a few things to keep in mind while conducting these tests manually:

- The flows work from start to end as expected.
- We show appropriate success and error messages to users.
- Charges are made or not made (free trial) as expected. You can verify this
  through the Stripe dashboard. However, this is not super important since
  our automated tests take care of such granular testing for us.
- Renewals cannot be tested manually and are tested in our automated tests.

#### Upgrading a Zulip organization

Here are some flows to test when upgrading a Zulip organization:

- When free trials are not enabled, i.e. `FREE_TRIAL_DAYS` is not set
  to any value in `dev_settings.py` (aka the default). You can
  double-check that the setting is disabled by verifying
  `./scripts/get-django-setting FREE_TRIAL_DAYS` returns 0.

  - Using a valid card number like `4242 4242 4242 4242`.
  - Using an invalid card number like `4000000000000341`, which will add the card
    to the customer account but the charge will fail.
    - Retry the upgrade after adding a new card by clicking on the retry upgrade
      link.
    - Retry the upgrade from scratch.

- Upgrade an organization when free trials are enabled. The free
  trials setting has been (possibly permanently) disabled in
  production for some time now, so testing this code path is not a
  priority. You can set `FREE_TRIAL_DAYS` to any number greater than
  `0` in `dev_settings.py` to enable free trials. There are two
  different flows to test here:
  - Right after the organization is created by following the instructions in the
    onboarding page.
    - Make sure that after the upgrade is complete the billing page shows a link to
      go to the organization.
  - By manually going to the `/billing` page and upgrading the organization.

#### Changing the card

The following flow should be tested when updating cards in our billing system:

- Go to the `/billing` page of an organization that has already been upgraded
  using a card. Try changing the card to another valid card such as
  `5555555555554444`.
  - Make sure that the flow completes without any errors and that the new card
    details are now shown on the billing page instead of the older card.
- You can also try adding a card number that results in it getting attached to
  the customer's account but charges fail. However, to test this, you need pending
  invoices since we try to charge for pending invoices when the card is updated.
  This is tested in our automated tests so it is not strictly necessary to test this
  manually.

## Upgrading Stripe API versions

Stripe makes pretty regular updates to their API. The process for upgrading
our code is:

- Go to the [Stripe Dashboard](https://dashboard.stripe.com/developers) in
  your Stripe account.
- Upgrade the API version.
- Run `tools/test-backend --generate-stripe-fixtures`.
- Fix any failing tests, and manually look through `git diff` to understand
  the changes. Ensure that there are no material changes.
- Update the value of `STRIPE_API_VERSION` in `corporate/lib/stripe.py`.
- Commit the changes, and open a PR.
- Ask Tim Abbott to upgrade the API version on the
  [Stripe Dashboard](https://dashboard.stripe.com/developers) for Zulip's official
  Stripe account.

We currently aren't set up to do version upgrades where there are breaking
changes, though breaking changes should be unlikely given the parts of the
product we use. The main remaining work for handling breaking version upgrades
is ensuring that we set the stripe version in our API calls.
Stripe's documentation for
[Upgrading your API version](https://stripe.com/docs/upgrades#how-can-i-upgrade-my-api)
has some additional information.
