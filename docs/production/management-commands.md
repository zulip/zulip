# Management commands

Zulip has a large library of [Django management
commands](https://docs.djangoproject.com/en/1.8/ref/django-admin/#django-admin-and-manage-py).
To use them, you will want to be logged in as the `zulip` user and for
the purposes of this documentation, we assume the current working
directory is `/home/zulip/deployments/current`.

Below, we show several useful examples, but there are more than 100
in total.  We recommend skimming the usage docs (or if there are none,
the code) of a management command before using it, since they are
generally less polished and more designed for expert use than the rest
of the Zulip system.

## Running management commands

Many management commands require the Zulip realm/organization to
interact with as an argument, which you can specify via numeric or
string ID.

You can see all the organizations on your Zulip server using
`./manage.py list_realms`.

```
zulip@zulip:~$ /home/zulip/deployments/current/manage.py list_realms
id    string_id                                name
--    ---------                                ----
1     zulipinternal                            None
2                                              Zulip Community
```

(Note that every Zulip server has a special `zulipinternal` realm containing
system-internal bots like `welcome-bot`; you are unlikely to need to
interact with that realm.)

Unless you are
[hosting multiple organizations on your Zulip server](../production/multiple-organizations.md),
your single Zulip organization on the root domain will have the empty
string (`''`) as its `string_id`.  So you can run e.g.:
```
zulip@zulip:~$ /home/zulip/deployments/current/manage.py show_admins -r ''
```

Otherwise, the `string_id` will correspond to the organization's
subdomain.  E.g. on `it.zulip.example.com`, use
`/home/zulip/deployments/current/manage.py show_admins -r it`.

## manage.py shell

You can get an iPython shell with full access to code within the Zulip
project using `manage.py shell`, e.g., you can do the following to
change a user's email address:

```
$ /home/zulip/deployments/current/manage.py shell
In [1]: user_profile = get_user_profile_by_email("email@example.com")
In [2]: do_change_user_delivery_email(user_profile, "new_email@example.com")
```

### manage.py dbshell

This will start a postgres shell connected to the Zulip database.

## Grant administrator access

You can make any user a realm administrator on the command line with
the `knight` management command:

```
./manage.py knight username@example.com -f
```

### Creating API super users with manage.py

If you need to manage the IRC, Jabber, or Zephyr mirrors, you will
need to create API super users.  To do this, use `./manage.py knight`
with the `--permission=api_super_user` argument.  See the respective
integration scripts for these mirrors (under
[`zulip/integrations/`][integrations-source] in the [Zulip Python API
repo][python-api-repo]) for further detail on these.

[integrations-source]: https://github.com/zulip/python-zulip-api/tree/master/zulip/integrations
[python-api-repo]: https://github.com/zulip/python-zulip-api

### Exporting users and realms with manage.py export

If you need to do an export of a single user or of an entire realm, we
have tools in `management/` that essentially export Zulip data to the
file system.

`export_single_user.py` exports the message history and realm-public
metadata for a single Zulip user (including that user's *received*
messages as well as their sent messages).

A good overview of the process for exporting a single realm when
moving a realm to a new server (without moving a full database dump)
is in
[management/export.py](https://github.com/zulip/zulip/blob/master/zerver/management/commands/export.py). We
recommend you read the comment there for words of wisdom on speed,
what is and is not exported, what will break upon a move to a new
server, and suggested procedure.

## Other useful manage.py commands

There are dozens of useful management commands under
`zerver/management/commands/`.  We detail a few here:

* `manage.py help`: Lists all available management commands.
* `manage.py send_custom_email`: Can be used to send an email to a set
  of users.  The `--help` documents how to run it from a `manage.py
  shell` for use with more complex programmatically computed sets of
  users.
* `manage.py send_password_reset_email`: Sends password reset email(s)
  to one or more users.
* `manage.py change_user_email`: Change a user's email address.

All of our management commands have internal documentation available
via `manage.py command_name --help`.
