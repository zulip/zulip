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

Nearly all the billing-relevant code lives in `zilencer/`.

## General architecture

Notes:
* Anything that talks directly to Stripe should go in
  `zilencer/lib/stripe.py`.
* We generally try to store billing-related data in Stripe, rather than in
  Zulip database tables. We'd rather pay the penalty of making extra stripe
  API requests than deal with keeping two sources of data in sync.

The two main billing-related states for a realm are "have never had a
billing relationship with Zulip" and its opposite. This is determined by
`Customer.objects.filter(realm=realm).exists()`.  If a realm doesn't have a
billing relationship, all the messaging, screens, etc. are geared towards
making it easy to upgrade. If a realm does have a billing relationship, all
the screens are geared toward making it easy to access current and
historical billing information.

Note that having a billing relationship doesn't necessarily mean they are on
a paid plan, or have been in the past. E.g. adding a coupon for a potential
customer requires creating a Customer object.

Notes:
* When manually testing, I find I often run `Customer.objects.all().delete()`
  to reset the state.
* 4242424242424242 is Stripe's test credit card, also useful for manually
  testing. You can put anything in the address fields, any future expiry
  date, and anything for the CVV code.
