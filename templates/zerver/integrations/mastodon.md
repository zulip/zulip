Fetch public posts (sometimes called "toots") of individual accounts or
federated hashtags from Mastodon in Zulip! While Zulip doesn't integrate
directly with ActivityPub or the overall Fediverse, some ActivityPub servers,
like [Mastodon](https://joinmastodon.org/), publish various RSS feeds which can
be followed in Zulip using the [Zapier][1] or [RSS][2] integrations.

!!! tip ""

    Note that due to the various interactions and complexities of federation,
    following a hashtag on one homeserver does not guarantee all posts in the
    entire Fediverse will be included in the feed, only that all public posts
    that have federated to the instance in question will be included. This
    means you may get different results for the same hashtag, depending on
    which homeserver you choose to subscribe through.

1. Find the RSS feed for the entity you'd like to follow. Usually, this means appending
   `.rss` to its Mastodon URL.

    !!! tip ""

        For example, to follow Zulip's Mastodon account at
        `https://fosstodon.org/@zulip`, you would use
        `https://fosstodon.org/@zulip.rss`. To follow the #zulip hashtag at
        `https://fosstodon.org/tags/zulip`, you would use
        `https://fosstodon.org/tags/zulip.rss`.

1. Follow the [Zapier][1] (or if you prefer not to use Zapier, [plain RSS][2])
   integration guide using this feed URL.

{!congrats.md!}

![Mastodon posts in Zulip via Zapier](/static/images/integrations/mastodon/001.png)

[1]: ./zapier
[2]: ./rss
