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
feature. PGroonga supports all languages including Japanese, Chinese
and so on.

This section describes how to enable full-text search feature based on
PGroonga.

First, you [install PGroonga](http://pgroonga.github.io/install/).

Then, you grant `USAGE` privilege on `pgroonga` schema to `zulip`
user:

    GRANT USAGE ON SCHEMA pgroonga TO zulip;

See also:
[GRANT USAGE ON SCHEMA pgroonga](http://pgroonga.github.io/reference/grant-usage-on-schema-pgroonga.html)

Then, you set `True` to `USING_PGROONGA` in `local_settings.py`.

Before:

    # USING_PGROONGA = True

After:

    USING_PGROONGA = True

TODO: Describe how to enable PGroonga on installed Zulip.

Now, you can use full-text search against all languages.
