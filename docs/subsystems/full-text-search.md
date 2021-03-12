# Full-text search

Zulip supports full-text search, which can be combined arbitrarily
with Zulip's full suite of narrowing operators.  By default, it only
supports English text, but there is an experimental
[PGroonga](https://pgroonga.github.io/) integration that provides
full-text search for all languages.

The user interface and feature set for Zulip's full-text search is
documented in the "Search operators" documentation section in the Zulip
app's gear menu.

## The default full-text search implementation

Zulip's uses [PostgreSQL's built-in full-text search
feature](https://www.postgresql.org/docs/current/textsearch.html),
with a custom set of English stop words to improve the quality of the
search results.

In order to optimize the performance of delivering messages, the
full-text search index is updated for newly sent messages in the
background, after the message has been delivered.  This background
updating is done by
`puppet/zulip/files/postgresql/process_fts_updates`, which is usually
deployed on the database server, but could be deployed on an
application server instead.

## Multi-language full-text search

Zulip also supports using [PGroonga](https://pgroonga.github.io/) for
full-text search. While PostgreSQL's built-in full-text search feature
supports only one language at a time (in Zulip's case, English), the
PGroonga full-text search engine supports all languages
simultaneously, including Japanese and Chinese.  Once we have tested
this new backend sufficiently, we expect to switch Zulip deployments
to always use PGroonga.

### Enabling PGroonga

All steps in this section should be run as the `root` user; on most installs, this can be done by running `sudo -i`.

1. Alter the deployment setting:

        crudini --set /etc/zulip/zulip.conf machine pgroonga enabled

1. Update the deployment to respect that new setting:

        /home/zulip/deployments/current/scripts/zulip-puppet-apply

1. Edit `/etc/zulip/settings.py`, to add:

        USING_PGROONGA = True

1. Apply the PGroonga migrations:

        su zulip -c '/home/zulip/deployments/current/manage.py migrate pgroonga'

    Note that the migration may take a long time, and users will be
    unable to send new messages until the migration finishes.

1. Once the migrations are complete, restart Zulip:

        su zulip -c '/home/zulip/deployments/current/scripts/restart-server'


### Disabling PGroonga

1. Remove the PGroonga migration:

        su zulip -c '/home/zulip/deployments/current/manage.py migrate pgroonga zero'

    If you intend to re-enable PGroonga later, you can skip this step,
    at the cost of your Message table being slightly larger than it would
    be otherwise.

1. Edit `/etc/zulip/settings.py`, editing the line containing `USING_PGROONGA` to read:

        USING_PGROONGA = False

1. Restart Zulip:

        su zulip -c '/home/zulip/deployments/current/scripts/restart-server'

1. Finally, remove the deployment setting:

        crudini --del /etc/zulip/zulip.conf machine pgroonga
