# Caching in Zulip

Like any product with good performance characteristics, Zulip makes
extensive use of caching. This article talks about our caching
strategy, focusing on how we use `memcached` (since it's the thing
people generally think about when they ask about how a server does
caching).

## Backend caching with memcached

On the backend, Zulip uses `memcached`, a popular key-value store, for
caching. Our `memcached` caching helps let us optimize Zulip's
performance and scalability, since we often avoid overhead related
to database requests. With Django a typical trivial query can
often take 3-10x as long as a memcached fetch.

We use Django's built-in caching integration to manage talking to
memcached, and then a small application-layer library
(`zerver/lib/cache.py`).

It's common for projects using a caching system like `memcached` to
either have the codebase littered with explicit requests to interact
with the cache (or flush data from a cache), or (worse) be littered
with weird bugs that disappear after you flush memcached.

Caching bugs are a pain to track down, because they generally require
an extra and difficult-to-guess step to reproduce (namely, putting the
wrong data into the cache).

So we've designed our backend to ensure that if we write a small
amount of Zulip's core caching code correctly, then the code most developers
naturally write will both benefit from caching and not create any cache
consistency problems.

The overall result of this design is that for many places in the
Zulip's Django codebase, all one needs to do is call the standard
accessor functions for data (like `get_user` to fetch
user objects, or, for view code, functions like
`access_stream_by_id`, which checks permissions), and everything will
work great. The data fetches automatically benefit from `memcached`
caching, since those accessor methods have already been written to
transparently use Zulip's memcached caching system, and the developer
doesn't need to worry about whether the data returned is up-to-date:
it is. In the following sections, we'll talk about how we make this
work.

As a side note, the policy of using these accessor functions wherever
possible is a good idea, regardless of caching, because the functions
also generally take care of details you might not think about
(e.g. case-insensitive matching of stream names or email addresses).
It's amazing how slightly tricky logic that's duplicated in several
places invariably ends up buggy in some of those places, and in
aggregate we call these accessor functions hundreds of times in
Zulip. But the caching is certainly a nice bonus.

### The core implementation

The `get_user` function is a pretty typical piece of code using this
framework; as you can see, it's very little code on top of our
`cache_with_key` decorator:

```python
def user_profile_cache_key_id(email: str, realm_id: int) -> str:
    return f"user_profile:{hashlib.sha1(email.strip().encode()).hexdigest()}:{realm_id}"

def user_profile_cache_key(email: str, realm: "Realm") -> str:
    return user_profile_cache_key_id(email, realm.id)

@cache_with_key(user_profile_cache_key, timeout=3600 * 24 * 7)
def get_user(email: str, realm: Realm) -> UserProfile:
    return UserProfile.objects.select_related("realm", "bot_owner").get(
        email__iexact=email.strip(), realm=realm
    )
```

This decorator implements a pretty classic caching paradigm:

- The `user_profile_cache_key` function defines a unique map from a
  canonical form of its arguments to a string. These strings are
  namespaced (the `user_profile:` part) so that they won't overlap
  with other caches, and encode the arguments so that two uses of this
  cache won't overlap. In this case, a hash of the email address and
  realm ID are those canonicalized arguments. (The `make_safe_digest`
  is important to ensure we don't send special characters to
  memcached). And we have two versions, depending whether the caller
  has access to a `Realm` or just a `realm_id`.
- When `get_user` is called, `cache_with_key` will compute the key,
  and do a Django `cache_get` query for the key (which goes to
  memcached). If the key is in the cache, it just returns the value.
  Otherwise, it fetches the value from the database (using the actual
  code in the body of `get_user`), and then stores the value back to
  that memcached key before returning the result to the caller.
- Cache entries expire after the timeout; in this case, a week.
  Though in frequently deployed environments like chat.zulip.org,
  often cache entries will stop being used long before that, because
  `KEY_PREFIX` is rotated every time we deploy to production; see
  below for details.

We use this decorator in about 30 places in Zulip, and it saves a
huge amount of otherwise very self-similar caching code.

### Cautions

The one thing to be really careful with in using `cache_with_key` is
that if an item is in the cache, the body of `get_user` (above) is
never called. This means some things that might seem like clever code
reuse are actually a really bad idea. For example:

- Don't add a `get_active_user` function that uses the same cache key
  function as `get_user` (but with a different query that filters our
  deactivated users). If one called `get_active_user` to access a
  deactivated user, the right thing would happen, but if you called
  `get_user` to access that user first, then the `get_active_user`
  function would happily return the user from the cache, without ever
  doing your more restrictive query.

So remember: Use separate cache key functions for different data sets,
even if they feature the same objects.

### Cache invalidation after writes

The caching strategy described above works pretty well for anything
where the state it's storing is immutable (i.e. never changes). With
mutable state, one needs to do something to ensure that the Python
processes don't end up fetching stale data from the cache after a
write to the database.

We handle this using Django's longstanding
[post_save signals][post-save-signals] feature. Django signals let
you configure some code to run every time Django does something (for
`post_save`, right after any write to the database using Django's
`.save()`).

There's a handful of lines in `zerver/models.py` like these that
configure this:

```python
post_save.connect(flush_realm, sender=Realm)
post_save.connect(flush_user_profile, sender=UserProfile)
```

Once this `post_save` hook is registered, whenever one calls
`user_profile.save(...)` with a UserProfile object in our Django
project, Django will call the `flush_user_profile` function. Zulip is
systematic about using the standard Django `.save()` function for
modifying `user_profile` objects (and passing the `update_fields`
argument to `.save()` consistently, which encodes which fields on an
object changed). This means that all we have to do is write those
cache-flushing functions correctly, and people writing Zulip code
won't need to think about (or even know about!) the caching.

Each of those flush functions basically just computes the list of
cache keys that might contain data that was modified by the
`.save(...)` call (based on the object changed and the `update_fields`
data), and then sends a bulk delete request to `memcached` to remove
those keys from the cache (if present).

Maintaining these flush functions requires some care (every time we
add a new cache, we need to look through them), but overall it's a
pretty simple algorithm: If the changed data appears in any form in a
given cache key, that cache key needs to be cleared. E.g. the
`active_user_ids_cache_key` cache for a realm needs to be flushed
whenever a new user is created in that realm, or user is
deactivated/reactivated, even though it's just a list of IDs and thus
doesn't explicitly contain the `is_active` flag.

Once you understand how that works, it's pretty easy to reason about
when a particular flush function should clear a particular cache; so
the main thing that requires care is making sure we remember to reason
about that when changing cache semantics.

But the overall benefit of this cache system is that almost all the
code in Zulip just needs to modify Django model objects and call
`.save()`, and the caching system will do the right thing.

### Production deployments and database migrations

When upgrading a Zulip server, it's important to avoid having one
version of the code interact with cached objects from another version
that has a different data layout. In Zulip, we avoid this through
some clever caching strategies. Each "deployment directory" for Zulip
in production has inside it a `var/remote_cache_prefix` file,
containing a cache prefix (`KEY_PREFIX` in the code) that is
automatically appended to the start of any cache keys accessed by that
deployment directory (this is all handled internally by
`zerver/lib/cache.py`).

This completely solves the problem of potentially having contamination
from inconsistent versions of the source code / data formats in the cache.

### Automated testing and memcached

For Zulip's `test-backend` unit tests, we use the same strategy. In
particular, we just edit `KEY_PREFIX` before each unit test; this
means each of the thousands of test cases in Zulip has its own
independent memcached key namespace on each run of the unit tests. As
a result, we never have to worry about memcached caching causing
problems across multiple tests.

This is a really important detail. It makes it possible for us to do
assertions in our tests on the number of database queries or memcached
queries that are done as part of a particular function/route, and have
those checks consistently get the same result (those tests are great
for catching bugs where we accidentally do database queries in a
loop). And it means one can debug failures in the test suite without
having to consider the possibility that memcached is somehow confusing
the situation.

Further, this `KEY_PREFIX` model means that running the backend tests
won't potentially conflict with whatever you're doing in a Zulip
development environment on the same machine, which also saves a ton of
time when debugging, since developers don't need to think about things
like whether some test changed Hamlet's email address and that's why
login is broken.

More full-stack test suites like `test-js-with-puppeteer` or `test-api`
use a similar strategy (set a random `KEY_PREFIX` at the start of the
test run).

### Manual testing and memcached

Zulip's development environment will automatically flush (delete all
keys in) `memcached` when provisioning and when starting `run-dev`.
You can run the server with that behavior disabled using
`tools/run-dev --no-clear-memcached`.

### Performance

One thing be careful about with memcached queries is to avoid doing
them in loops (the same applies for database queries!). Instead, one
should use a bulk query. We have a fancy function,
`generate_bulk_cached_fetch`, which is super magical and handles this
for us, with support for a bunch of fancy features like marshalling
data before/after going into the cache (e.g. to compress `message`
objects to minimize data transfer between Django and memcached).

## In-process caching in Django

We generally try to avoid in-process backend caching in Zulip's Django
codebase, because every Zulip production installation involves
multiple servers. We do have a few, however:

- `@return_same_value_during_entire_request`: We use this decorator to
  cache values in memory during the lifetime of a request. We use this
  for linkifiers and display recipients. The middleware knows how to
  flush the relevant in-memory caches at the start of a request.
- Caches of various data, like the `SourceMap` object, that are
  expensive to construct, not needed for most requests, and don't
  change once a Zulip server has been deployed in production.

## Browser caching of state

Zulip makes extensive use of caching of data in the browser and mobile
apps; details like which users exist, with metadata like names and
avatars, similar details for streams, recent message history, etc.

This data is fetched in the `/register` endpoint (or `page_params`
for the web app), and kept correct over time. The key to keeping these
state up to date is Zulip's
[real-time events system](events-system.md), which
allows the server to notify clients whenever state that might be
cached by clients is changed. Clients are responsible for handling
the events, updating their state, and rerendering any UI components
that might display the modified state.

[post-save-signals]: https://docs.djangoproject.com/en/3.2/ref/signals/#post-save
