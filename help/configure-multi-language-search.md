# Configure multi-language search

Zulip supports [full-text search](/help/search-for-messages), which can be
combined arbitrarily with Zulip's full suite of narrowing operators. By default,
Zulip search only supports English text, using [PostgreSQL's built-in full-text
search feature](https://www.postgresql.org/docs/current/textsearch.html), with a
custom set of English stop words to improve the quality of the search results.

Self-hosted Zulip organizations can instead set up an experimental
[PGroonga](https://pgroonga.github.io/) integration that provides full-text
search for all languages simultaneously, including Japanese and Chinese. See
[here](https://zulip.readthedocs.io/en/stable/subsystems/full-text-search.html#multi-language-full-text-search)
for setup instructions.

## Related articles

* [Configure organization language for automated messages and invitation emails][org-lang]
* [Searching for messages](/help/search-for-messages)

[org-lang]: /help/configure-organization-language
