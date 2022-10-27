You attempted to use the `DevAuthBackend` authentication method, which
is used for logging in without a password in the Zulip development
environment.

This backend is not available for this realm, either because:

* This Zulip server is configured as a production server.
* `DevAuthBackend` is disabled in `AUTHENTICATION_BACKENDS` in `{{
settings_path }}`.
* You disabled this authentication backend in [this realm's
  authentication settings](/help/configure-authentication-methods).
