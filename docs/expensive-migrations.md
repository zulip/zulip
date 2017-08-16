# Running expensive migrations early

If you'd like to run the major database migrations included in the
Zulip 1.7 release early, before you start the upgrade process, you can
do the following:

* Log into your zulip server as the `zulip` user (or as `root` and
  then run `su zulip` to drop privileges), and `cd
  /home/zulip/deployments/current`
* Run `./manage.py dbshell`.  This will open a shell connected to the
  Postgres database.
* In the postgres shell, run the following commands:

```
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
    WHERE (flags & 8) != 0 OR (FLAGS & 16) != 0;

    CREATE INDEX CONCURRENTLY
    zerver_usermessage_unread_message_id
    ON zerver_usermessage (user_profile_id, message_id)
    WHERE (flags & 1) = 0;
```

Once these have finished, you can proceed with installing zulip 1.7.

To help you estimate how long these will take on your server, creating
the first 4 indexes took about 1 minute each with chat.zulip.org's 75M
UserMessage rows (from `select COUNT(*) from zerver_usermessage;` in
the `manage.py dbshell`), with no user-facing service disruption.  The
final, "unread_message" index took more like 10 minutes.

