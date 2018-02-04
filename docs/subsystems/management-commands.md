# Management commands

Zulip has a number of [Django management commands][django-docs] that
live under `{zerver,zilencer,analytics}/management/commands/`.

If you need some Python code to run with a Zulip context (access to
the database, etc.) in a script, it should probably go in a management
command.  The key thing distinguishing these from production scripts
(`scripts/`) and development scripts (`tools/`) is that management
commands can access the database.

While Zulip takes advantage of built-in Django management commands for
things like managing Django migrations, we also have dozens that we've
written for a range of purposes:

* Cron jobs to do regular updates, e.g. `update_analytics_counts.py`,
  `sync_ldap_user_data`, etc.
* Useful parts of provisioning or upgrading a Zulip development
  environment or server, e.g. `makemessages`, `compilemessages`,
  `populate_db`, `fill_memcached_caches`, etc.
* The actual scripts run by supervisord to run the persistent
  processes in a Zulip server, e.g. `runtornado` and `process_queue`.
* For a sysadmin to verify a Zulip server's configuration during
installation, e.g. `checkconfig`, `send_test_email`.
* As the interface for doing those rare operations that don't have a
  UI yet, e.g. `deactivate_realm`, `reactivate_realm`,
  `change_user_email` (for the case where the user doesn't control the
  old email address).
* For a sysadmin to easily interact with and script common possible
  changes they might want to make to the database on a Zulip server.
  E.g. `send_password_reset_email`, `export`, `purge_queue`.

## Writing management commands

It's generally pretty easy to template off an existing management
command to write a new one.  Some good examples are
`change_user_email` and `deactivate_realm`.  The Django documentation
is good, but we have a few pieces advice specific to the Zulip
project.

* If you need to access a realm or user, use the `ZulipBaseCommand`
  class in `zerver/lib/management.py` so you don't need to write the
  tedious code of looking those objects up.  This is especially
  important for users, since the library handles the issues around
  looking up users by email well (if there's a unique user with that
  email, just modify it without requiring the user to specify the
  realm as well, but if there's a collision, throw a nice error).
* Avoid writing a lot of code in management commands; management
  commands are annoying to unit test, and thus easier to maintain if
  all the interesting logic is in a nice function that is unit tested
  (and ideally, also used in Zulip's existing code).  Look for code in
  `zerver/lib/` that already does what you need.  For most actions,
  you can just call a `do_change_foo` type function from
  `zerver/lib/actions.py` to do all the work; this is usually far
  better than manipulating the database correctly, since the library
  functions used by the UI are maintained to correctly live-update the
  UI if needed.

[django-docs]: https://docs.djangoproject.com/en/1.9/howto/custom-management-commands/
