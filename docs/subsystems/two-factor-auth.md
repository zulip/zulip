# Two Factor Authentication

Zulip uses [django-two-factor-auth][0] to integrate 2FA.

To enable 2FA, set `TWO_FACTOR_AUTHENTICATION_ENABLED` in settings to `True`,
then log into Zulip and add otp device from settings page. Once the device is
added, password based authentication will ask for one-time-password. In dev.,
this one-time-password will be printed to the console when you try to login.
Just copy-paste it into the form field to continue.

Direct dev. logins don't prompt for 2FA one-time-passwords, so to test 2FA in
development, make sure that you login using a password. You can get the
passwords for the default test users using `./manage.py print_initial_password`
command.

[0]: https://github.com/Bouke/django-two-factor-auth
