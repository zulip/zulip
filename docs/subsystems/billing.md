# Billing

Zulip uses a third party (Stripe) for billing, so working on the billing
system requires a little bit of setup.

To set up the development environment to work on the billing code:
* Create a Stripe account
* Go to <https://dashboard.stripe.com/account/apikeys>, and add the
  publishable key and secret key as `stripe_publishable_key` and
  `stripe_secret_key` to `zproject/dev-secrets.conf`.

Nearly all the billing-relevant code lives in `corporate/`.

## Upgrading Stripe API versions

Stripe makes pretty regular updates to their API. The process for upgrading
our code is:
* Go to <https://dashboard.stripe.com/developers> in your Stripe account.
* Upgrade the API version.
* Set `GENERATE_STRIPE_FIXTURES = True` in `test_stripe.py`.
* Run `tools/test-backend corporate/tests/test_stripe.py`
* Fix any failing tests, and manually look through `git diff` to understand
  the changes.
* If there are no material changes, commit the diff, and open a PR.
* Ask Rishi or Tim to go to <https://dashboard.stripe.com/developers> in the
  zulipchat Stripe account, and upgrade the API version there.

We currently aren't set up to do version upgrades where there are breaking
changes, though breaking changes should be unlikely given the parts of the
product we use. The main remaining work for handling breaking version upgrades
is ensuring that we set the stripe version in our API calls.
<https://stripe.com/docs/upgrades#how-can-i-upgrade-my-api> has some
additional information.
