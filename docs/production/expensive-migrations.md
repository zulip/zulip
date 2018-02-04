```eval_rst
:orphan:
```

# Running expensive migrations early

Zulip 1.7 contains some significant database migrations that can take
several minutes to run.

The upgrade process automatically minimizes disruption by running
these first, before beginning the user-facing downtime.  However, if
you'd like to watch the downtime phase of the upgrade closely, you
can run them manually before starting the upgrade:

1. Log into your Zulip server as the `zulip` user (or as `root` and
  then run `su zulip` to drop privileges), and `cd
  /home/zulip/deployments/current`
2. Run `./manage.py dbshell`.  This will open a shell connected to the
  Postgres database.
3. In the postgres shell, run the following commands:

        CREATE INDEX CONCURRENTLY
        zerver_usermessage_mentioned_message_id
        ON zerver_usermessage (user_profile_id, message_id)
        WHERE (flags & 8) != 0;

        CREATE INDEX CONCURRENTLY
        zerver_usermessage_starred_message_id
        ON zerver_usermessage (user_profile_id, message_id)
        WHERE (flags & 2) != 0;

        CREATE INDEX CONCURRENTLY
        zerver_usermessage_has_alert_word_message_id
        ON zerver_usermessage (user_profile_id, message_id)
        WHERE (flags & 512) != 0;

        CREATE INDEX CONCURRENTLY
        zerver_usermessage_wildcard_mentioned_message_id
        ON zerver_usermessage (user_profile_id, message_id)
        WHERE (flags & 8) != 0 OR (flags & 16) != 0;

        CREATE INDEX CONCURRENTLY
        zerver_usermessage_unread_message_id
        ON zerver_usermessage (user_profile_id, message_id)
        WHERE (flags & 1) = 0;

4. These will take some time to run, during which the server will
  continue to serve user traffic as usual with no disruption.  Once
  they finish, you can proceed with installing Zulip 1.7.

To help you estimate how long these will take on your server: count
the number of UserMessage rows, with `select COUNT(*) from zerver_usermessage;`
at the `./manage.py dbshell` prompt.  At the time these migrations
were run on chat.zulip.org, it had 75M UserMessage rows; the first 4
indexes took about 1 minute each to create, and the final,
"unread_message" index took more like 10 minutes.
