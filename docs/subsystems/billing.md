# Billing (Development)

This section deals with developing and testing the billing system.

## Common setup

- Create a Stripe account
  - Make sure that the country of your Stripe account is set to USA when you create the account.
  - You might probably need to use a VPN for this.
- Ensure that the [API version](https://stripe.com/docs/api/versioning) of
  your Stripe account is same as `STRIPE_API_VERSION` defined in
  `corporate/lib/stripe.py`. You can upgrade to a higher version from
  the Stripe dashboard.
- Set the private API key.
  - Go to <https://dashboard.stripe.com/account/apikeys>
  - Add `stripe_secret_key` to `zproject/dev-secrets.conf`.

## Manual testing

Manual testing involves testing the various flows like upgrade, card change etc manually through the browser. This is the bare minimum testing that you need to do when you review a PR or is working on adding a new feature.

### Setup

Apart from the common setup mentioned above, you also need to setup your dev environment to receive webhook events
from Stripe.

- Install Stripe CLI by following the instructions at <https://stripe.com/docs/webhooks/test> in your machine locally.
- Login to Stripe CLI by `stripe login`
- Run run the Stripe CLI to forward all the Stripe webhook events to our billing system webhook endpoint.
  `stripe listen --forward-to http://localhost:9991/stripe/webhook/`
- Wait for the `stripe listen` command in the previous step to output the webhook signing secret.
  - The signing secret would be used by our billing system to verify that the events that are sent to our webhook endpoint is sent by Stripe and not by an intruder. In production, there is no Stripe CLI, so the step for configuring this is a bit different. See the production section for more details.
- Copy the webhook signing secret and set it as `stripe_webhook_endpoint_secret` in `zproject/dev-secrets.conf`.
- The billing system is now all set to receive webhook events from Stripe.

### Test card numbers

Stripe provides various card numbers to test for specific responses from Stripe. Thee commonly used ones are mentioned in the documentation below wherever appropriate. The full list is available at <https://stripe.com/docs/testing>

### Flows to test

These are the flows that you can test manually from the browser.

- Upgrade a Zulip organization
  - Flows to test
    - When free trial is not enabled, ie `FREE_TRIAL_DAYS` is not set to any value in `dev_settings.py`. Free trial is rarely enabled. So when you are manually testing make sure that `FREE_TRIAL_DAYS` is not set to any value unless you want to test the free trial functionality.
      - Using a valid card number like `4242 4242 4242 4242`
      - Using an invalid card number like `4000000000000341` which will add the card to the Customer account but charge fails.
        - Retry the upgrade by adding a new card by clicking on the retry upgrade link.
        - Retry the upgrade from scratch.
    - Upgrade an organization when free trial is enabled. You can set `FREE_TRIAL_DAYS` to a number greater than `0` in `dev_settings.py` to enable free trial. This is a setting that is not commonly used.
      - There are two different flows to test here.
        - Right after the organization is created by following the instructions in the onboarding page.
          - Make sure that after the upgrade is complete the billing page shows a link to go to the organization.
        - By manually going to billing page and upgrading the organization.
  - What to test?
    - The flows work from start to end as expected.
    - We show appropriate success and error messages to users.
    - Charges are made or not made(free trial) as expected. You can check this through the Stripe dashboard. Though not that super important since we check these in automated tests anyway.
    - Testing that involves renewal and all is not possible through manual testing. It is taken care of in backend tests.
- Change the card
  - Flows to test
    - Go to the billing page of an organization that is upgraded using card. Then try changing the card to another valid card like `5555555555554444`.
      - Make sure that the flow completes without any error and the new card details is now shown in the billing page instead of the old card.
    - You can also try adding a card number that results in it getting attached to the customer but charges fails. But to test that you need pending invoices since we try to pay pending invoices when the card is changed. It's taken care of in backend tests so it's not super necessary to test manually.

## Upgrading Stripe API versions

Stripe makes pretty regular updates to their API. The process for upgrading
our code is:

- Go to <https://dashboard.stripe.com/developers> in your Stripe account.
- Upgrade the API version.
- Run `tools/test-backend --generate-stripe-fixtures`
- Fix any failing tests, and manually look through `git diff` to understand
  the changes. Ensure that there are no material changes.
- Update the value of `STRIPE_API_VERSION` in `corporate/lib/stripe.py`.
- Commit the diff, and open a PR.
- Ask to Tim to go to <https://dashboard.stripe.com/developers> in the
  zulipchat Stripe account, and upgrade the API version there.

We currently aren't set up to do version upgrades where there are breaking
changes, though breaking changes should be unlikely given the parts of the
product we use. The main remaining work for handling breaking version upgrades
is ensuring that we set the stripe version in our API calls.
<https://stripe.com/docs/upgrades#how-can-i-upgrade-my-api> has some
additional information.
