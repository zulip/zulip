Fetch public posts (sometimes called “toots”) of individual accounts or
federated hashtags from Mastodon in Zulip! While Zulip doesn't integrate
directly with ActivityPub or the overall Fediverse, some ActivityPub servers,
like [Mastodon](https://joinmastodon.org/), publish RSS feeds that can
be followed in Zulip using the [Zapier][1] or [RSS][2] integrations.

!!! warn ""

    Due to the complexities of Mastodon federation,
    following a hashtag on one homeserver does not guarantee that all posts in the
    entire Fediverse will be included in the feed.  Rather, all public posts
    that have federated to the instance in question will be included. This
    means you may get different results for the same hashtag, depending on
    which homeserver you choose to subscribe through.

1. Find the RSS feed for the account or hashtag you'd like to follow. Usually,
   this means appending `.rss` to its Mastodon URL.

    !!! tip ""

        For example, to follow Zulip's Mastodon account at
        `https://fosstodon.org/@zulip`, you would use
        `https://fosstodon.org/@zulip.rss`. To follow the **#zulip** hashtag at
        `https://fosstodon.org/tags/zulip`, you would use
        `https://fosstodon.org/tags/zulip.rss`.

1. Follow the [Zapier][1] integration guide (recommended) or the [plain RSS][2]
   integration guide using this feed URL.

{!congrats.md!}

![Mastodon posts in Zulip via Zapier](/static/images/integrations/mastodon/001.png)

[1]: ./zapier
[2]: ./rss
