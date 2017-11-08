# Full-text search

Zulip supports full-text search, which can be combined arbitrarily
with Zulip's full suite of narrowing operators.  By default, it only
supports English text, but there is an experimental
[PGroonga](http://pgroonga.github.io/) integration that provides
full-text search for all languages.

The user interface and feature set for Zulip's full-text search is
documented in the "Search operators" documentation section in the Zulip
app's gear menu.

## The default full-text search implementation

Zulip's uses [PostgreSQL's built-in full-text search
feature](http://www.postgresql.org/docs/current/static/textsearch.html),
with a custom set of English stop words to improve the quality of the
search results.

We use a small extension,
[tsearch_extras](https://github.com/zulip/tsearch_extras), for
highlighting of the matching words.  There is [some discussion of
removing this extension, at least as an
option](https://github.com/zulip/zulip/issues/467), so that Zulip can
be used with database-as-a-service platforms.

In order to optimize the performance of delivering messages, the
full-text search index is updated for newly sent messages in the
background, after the message has been delivered.  This background
updating is done by
`puppet/zulip/files/postgresql/process_fts_updates`, which is usually
deployed on the database server, but could be deployed on an
application server instead.

## An optional full-text search implementation

Zulip now supports using [PGroonga](http://pgroonga.github.io/) for
full-text search. PGroonga is a PostgreSQL extension that provides
full-text search feature. PostgreSQL's built-in full-text search
feature supports only one language at a time (in Zulip's case,
English).  PGroonga supports all languages simultaneously, including
Japanese, Chinese and so on, all at once.  We expect to migrate
Zulip's full-text search to only support PGroonga once we have tested
this new extension fully.

The following processes should be executed as the root user. Run:

    sudo -i

### How to enable full-text search across all languages

This section describes how to enable using PGroonga to back the
full-text search feature.

To install PGroonga, add `pgroonga = enabled` in the `[machine]`
section in `/etc/zulip/zulip.conf`:

    [machine]
    ...
    pgroonga = enabled

And then run as root:

    /home/zulip/deployments/current/scripts/zulip-puppet-apply

Then, add `USING_PGROONGA = true` in `/etc/zulip/settings.py`:

    USING_PGROONGA = True

And apply the PGroonga migrations:

    cd /srv/zulip
    ./manage.py migrate pgroonga

Note that the migration may take a long time, and you can't send new
messages until the migration finishes.

Once the migrations are complete, restart Zulip:

    su zulip -c /home/zulip/deployments/current/scripts/restart-server

Now, you can use full-text search across all languages.

### How to disable full-text search across all languages

This section describes how to disable full-text search feature based
on PGroonga.

If you want to fully remove PGroonga, first you need to remove the
PGroonga column (as above, this will take a long time and no messages
can be sent while it is running).  If you intend to re-enable PGroonga
later, you can skip this step (at the cost of your Message table being
slightly larger than it would be otherwise).

    /home/zulip/deployments/current/manage.py migrate pgroonga zero

Then, set `USING_PGROONGA = False` in `/etc/zulip/settings.py`:

    USING_PGROONGA = False

And, restart Zulip:

    su zulip -c /home/zulip/deployments/current/scripts/restart-server

Now, full-text search feature based on PGroonga is disabled.  If you'd
like, you can also remove the `pgroonga = enabled` line in
`/etc/zulip/zulip.conf` and uninstall the `pgroonga` packages.
