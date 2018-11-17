# Billing

Zulip uses a third party (Stripe) for billing, so working on the billing
system requires a little bit of setup.

To set up the development environment to work on the billing code:
* Create a Stripe account
* Go to <https://dashboard.stripe.com/account/apikeys>, and add the
  publishable key and secret key as `stripe_publishable_key` and
  `stripe_secret_key` to `zproject/dev-secrets.conf`.
* Run `./manage.py setup_stripe`.

It is safe to run `manage.py setup_stripe` multiple times.

Nearly all the billing-relevant code lives in `corporate/`.

## General architecture

Notes:
* Anything that talks directly to Stripe should go in
  `corporate/lib/stripe.py`.
* We generally try to store billing-related data in Stripe, rather than in
  Zulip database tables. We'd rather pay the penalty of making extra stripe
  API requests than deal with keeping two sources of data in sync.
* A realm should have a customer object in Stripe if and only if it has a
  `Customer` object in Zulip.

The two main billing-related states for a realm are "have never successfully
been charged for anything" and its opposite. This is determined by whether
the `realm` has a corresponding `Customer` object with
`has_billing_relationship=True`. There are only a few cases where a `realm`
might have a `Customer` object with `has_billing_relationship=False`:
* They are approved as a non-profit or otherwise have a partial discount,
  but haven't entered any payment info.
* They entered valid payment info, but the initial charge failed (rare but
  possible).

If a realm doesn't have a billing relationship, all the messaging, screens,
etc. are geared towards making it easy to upgrade. If a realm does have a
billing relationship, all the screens are geared toward making it easy to
access current and historical billing information.

Note that having a billing relationship doesn't necessarily mean they are
currently on a paid plan, or that they currently have a card on file.

Notes:
* When manually testing, I find I often run `Customer.objects.all().delete()`
  to reset the state.
* 4242424242424242 is Stripe's test credit card, also useful for manually
  testing. You can put anything in the address fields, any future expiry
  date, and anything for the CVV code.
  <https://stripe.com/docs/testing#cards-responses> has some other fun ones.

## BillingProcessor

The general strategy here is that billing-relevant events get written to
RealmAuditLog with `requires_billing_update = True`, and then a worker
goes through, reads RealmAuditLog row by row, and makes the appropriate
updates in Stripe (in order), keeping track of its state in
`BillingProcessor`. An invariant is that it cannot be important when
exactly the worker gets around to making the update in Stripe, as long
as the updates for each customer (realm) are made in `RealmAuditLog.id` order.

Almost all the complexity in the code is due to error handling. We
distinguish three kinds of errors:
* Transient errors, like rate limiting or network failures, where we just
  wait a bit and try again.
* Card decline errors (see below)
* Everything else (e.g. misconfigured API keys, errors thrown by buggy code,
  etc.), where we just throw an exception and stop the worker.

We use the following strategy for card decline errors. There is a global
BillingProcessor (with `realm=None`) that processes RealmAuditLog
entries for every customer (realm). If it runs into a card decline error on
some entry, it gives up on that entry and (temporarily) all future entries
of that realm, and spins off a realm-specific BillingProcessor that
marks that realm as needing manual attention. When whatever issue has been
corrected, the realm-specific BillingProcessor completes any
realm-specific RealmAuditLog entries, and then deletes itself.

Notes for manually resolving errors:
* `BillingProcessor.objects.filter(state='stalled')` is always safe to
  handle manually.
* `BillingProcessor.objects.filter(state='started')` is safe to handle
  manually only if the billing process worker is not running.
* After resolving the issue, set the processor's state to `done`.
* Stripe's idempotency keys are only valid for 24 hours. So be mindful of
  that if manually cleaning something up more than 24 hours after the error
  occured.

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
changes. The main remaining work is ensuring that we set the stripe version
in our API calls.
<https://stripe.com/docs/upgrades#how-can-i-upgrade-my-api> has some
additional information.
