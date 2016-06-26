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

See [the option PGroonga pull
request](https://github.com/zulip/zulip/pull/700) for details on the
status of the PGroonga integration.
