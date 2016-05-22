# Full-text search

Zulip supports full-text search, which can be combined arbitrarily
with Zulip's full suite of narrowing operators.  By default, it only
supports English text, but there is an experimental
[PGroonga](http://pgroonga.github.io/) integration that provides
full-text search for all languages.

The user interface and feature set for Zulip's full-text search is
documented in the "Search help" documentation section in the Zulip
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

Zulip also supports [PGroonga](http://pgroonga.github.io/). PGroonga
is a PostgreSQL extension that provides full-text search
feature. PostgreSQL's built-in full-text search feature supports only
one language at a time. PGroonga supports all languages including
Japanese, Chinese and so on at a time.

### How to enable full-text search against all languages

This section describes how to enable full-text search feature based on
PGroonga.

You [install PGroonga](http://pgroonga.github.io/install/).

You enable PGroonga by `scripts/setup/enable-pgroonga`:

    /home/zulip/deployments/current/scripts/setup/enable-pgroonga

You set `True` to `USING_PGROONGA` in `/etc/zulip/settings.py`:

Before:

    # USING_PGROONGA = True

After:

    USING_PGROONGA = True

You restart Zulip:

    su zulip -c /home/zulip/deployments/current/scripts/restart-server

Now, you can use full-text search against all languages.

### How to disable full-text search against all languages

This section describes how to disable full-text search feature based
on PGroonga.

You set `False` to `USING_PGROONGA` in
`local_settings.py`. `USING_PGROONGA` is `False` by default. So you
just comment it out:

Before:

    USING_PGROONGA = True

After:

    # USING_PGROONGA = True

You restart Zulip:

    su zulip -c /home/zulip/deployments/current/scripts/restart-server

You disable PGroonga by `scripts/setup/disable-pgroonga`:

    /home/zulip/deployments/current/scripts/setup/disable-pgroonga

Now, full-text search feature based on PGroonga is disabled.
