# Management commands

Sometimes, you need to modify or inspect Zulip data from the command
line. To help with this, Zulip ships with over 100 command-line tools
implemented using the [Django management commands
framework][django-management].

## Running management commands

Start by logging in as the `zulip` user on the Zulip server. Then run
them as follows:

```bash
cd /home/zulip/deployments/current

# Start by reading the help
./manage.py <command_name> --help

# Once you've determined this is the command for you, run it!
./manage.py <command_name> <args>
```

A full list of commands is available via `./manage.py help`; you'll
primarily want to use those in the `[zerver]` section as those are the
ones specifically built for Zulip.

As a warning, some of them are designed for specific use cases and may
cause problems if run in other situations. If you're not sure, it's
worth reading the documentation (or the code, usually available at
`zerver/management/commands/`; they're generally very simple programs).

### Accessing an organization's `string_id`

Since Zulip supports hosting multiple organizations on a single
server, many management commands require you specify which
organization ("realm") you'd like to modify, either via numerical or
string ID (usually the subdomain).

You can see all the organizations on your Zulip server using
`./manage.py list_realms`.

```console
zulip@zulip:~$ /home/zulip/deployments/current/manage.py list_realms
id    string_id                                name
--    ---------                                ----
1     zulipinternal                            None
2                                              Zulip Community
```

(Note that every Zulip server has a special `zulipinternal` realm
containing system-internal bots like `Notification Bot`; you are
unlikely to ever need to interact with that realm.)

Unless you are
[hosting multiple organizations on your Zulip server](multiple-organizations.md),
your single Zulip organization on the root domain will have the empty
string (`''`) as its `string_id`. So you can run e.g.:

```console
zulip@zulip:~$ /home/zulip/deployments/current/manage.py show_admins -r ''
```

Otherwise, the `string_id` will correspond to the organization's
subdomain. E.g. on `it.zulip.example.com`, use
`/home/zulip/deployments/current/manage.py show_admins -r it`.

## manage.py shell

If you need to query or edit data directly in the Zulip database, the
best way to do this is with Django's built-in management shell.

You can get an IPython shell with full access to code within the Zulip
project using `manage.py shell`, e.g., you can do the following to
change a user's email address:

```console
$ cd /home/zulip/deployments/current/
$ ./manage.py shell
In [1]: user_profile = get_user_profile_by_email("email@example.com")
In [2]: do_change_user_delivery_email(user_profile, "new_email@example.com")
```

Any Django tutorial can give you helpful advice on querying and
formatting data from Zulip's tables for inspection; Zulip's own
[new feature tutorial](../tutorials/new-feature-tutorial.md) should help
you understand how the codebase is organized.

We recommend against directly editing objects and saving them using
Django's `object.save()`. While this will save your changes to the
database, for most objects, in addition to saving the changes to the
database, one may also need to flush caches, notify the apps and open
browser windows, and record the change in Zulip's `RealmAuditLog`
audit history table. For almost any data change you want to do, there
is already a function in `zerver.actions` with a name like
`do_change_full_name` that updates that field and notifies clients
correctly.

For convenience, Zulip automatically imports `zerver.models`
into every management shell; if you need to
access other functions, you'll need to import them yourself.

## Other useful manage.py commands

There are dozens of useful management commands under
`zerver/management/commands/`. We detail a few here:

- `./manage.py help`: Lists all available management commands.
- `./manage.py dbshell`: If you're more comfortable with raw SQL than
  Python, this will open a PostgreSQL SQL shell connected to the Zulip
  server's database. Beware of changing data; editing data directly
  with SQL will often not behave correctly because PostgreSQL doesn't
  know to flush Zulip's caches or notify browsers of changes.
- `./manage.py send_custom_email`: Can be used to send an email to a set
  of users. The `--help` documents how to run it from a
  `manage.py shell` for use with more complex programmatically
  computed sets of users.
- `./manage.py send_password_reset_email`: Sends password reset email(s)
  to one or more users.
- `./manage.py change_realm_subdomain`: Change subdomain of a realm.
- `./manage.py change_user_email`: Change a user's email address.
- `./manage.py change_user_role`: Can change are user's role
  (easier done [via the
  UI](https://zulip.com/help/change-a-users-role)) or give bots the
  `can_forge_sender` permission, which is needed for certain special API features.
- `./manage.py export_single_user`: does a limited version of the [main
  export tools](export-and-import.md) containing just
  the messages accessible by a single user.
- `./manage.py unarchive_channel`:
  [Reactivates](https://zulip.com/help/archive-a-stream#unarchiving-archived-streams)
  an archived channel.
- `./manage.py reactivate_realm`: Reactivates a realm.
- `./manage.py deactivate_user`: Deactivates a user. This can be done
  more easily in Zulip's organization administrator UI.
- `./manage.py delete_user`: Completely delete a user from the database.
  For most purposes, deactivating users is preferred, since that does not
  alter message history for other users.
  See the `./manage.py delete_user --help` documentation for details.
- `./manage.py clear_auth_rate_limit_history`: If a user failed authentication
  attempts too many times and further attempts are disallowed by the rate limiter,
  this can be used to reset the limit.

All of our management commands have internal documentation available
via `manage.py command_name --help`.

## Custom management commands

Zulip supports several mechanisms for running custom code on a
self-hosted Zulip server:

- Using an existing [integration][integrations] or writing your own
  [webhook integration][webhook-integrations] or [bot][writing-bots].
- Writing a program using the [Zulip API][zulip-api].
- [Modifying the Zulip server][modifying-zulip].
- Using the interactive [management shell](#managepy-shell),
  documented above, for one-time work or prototyping.
- Writing a custom management command, detailed here.

Custom management commands are Python 3 programs that run inside
Zulip's context, so that they can access its libraries, database, and
code freely. They can be the best choice when you want to run custom
code that is not permitted by Zulip's security model (and thus can't
be done more easily using the [REST API][zulip-api]) and that you
might want to run often (and so the interactive `manage.py shell` is
not suitable, though we recommend using the management shell to
prototype queries).

Our developer documentation on [writing management
commands][management-commands-dev] explains how to write them.

Simply writing the command inside a `deployments/` directory is not
ideal, because a new such directory is created every time you upgrade
the Zulip server.

Instead, we recommend deploying custom management commands either via
the [modifying Zulip][modifying-zulip] process or by storing them in
`/etc/zulip` (so they are included in
[backups](export-and-import.md#backups)) and then
symlinking them into
`/home/zulip/deployments/current/zerver/management/` after each
upgrade.

[modifying-zulip]: modify.md
[writing-bots]: https://zulip.com/api/writing-bots
[integrations]: https://zulip.com/integrations
[zulip-api]: https://zulip.com/api/rest
[webhook-integrations]: https://zulip.com/api/incoming-webhooks-overview
[management-commands-dev]: ../subsystems/management-commands.md
[django-management]: https://docs.djangoproject.com/en/3.2/ref/django-admin/#django-admin-and-manage-py
