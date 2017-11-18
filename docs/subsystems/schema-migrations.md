# Schema Migrations

Zulip uses the [standard Django system for doing schema
migrations](https://docs.djangoproject.com/en/1.10/topics/migrations/).
There is some example usage in the [new feature
tutorial](../tutorials/new-feature-tutorial.html).

This page documents some important issues related to writing schema
migrations.

* **Naming**: Please provide clear names for new database migrations
  (e.g. `0072_realmauditlog_add_index_event_time.py`).  Since in the
  Django migrations system, the filename is the name for the
  migration, this just means moving the migration file to have a
  reasonable name.  Note that `tools/test-migrations` will fail in
  Travis CI if a migration has bad name of the form
  `0089_auto_20170710_1353.py`, which are what Django generates
  automatically for nontrivial database schema changes.

* **Large tables**: For large tables like Message and UserMessage, you
  want to take precautions when adding columns to the table,
  performing data backfills, or building indexes. We have a
  `zerver/lib/migrate.py` library to help with adding columns and
  backfilling data. For building indexes on these tables, we should do
  this using SQL with postgres's CONCURRENTLY keyword.

* **Numbering conflicts across branches**: If you've done your schema
  change in a branch, and meanwhile another schema change has taken
  place, Django will now have two migrations with the same number. To
  fix this, you can either run `./tools/renumber-migrations` which
  renumbers your migration(s) and fixes up the "dependencies" entries in your
  migration(s), and then rewrite your git history as needed, or you can do it
  manually. There is a tutorial [here](migration-renumbering.html) that
  walks you though that process.

* **Atomicity**.  By default, each Django migration is run atomically
  inside a transaction.  This can be problematic if one wants to do
  something in a migration that touches a lot of data and would best
  be done in batches of e.g. 1000 objects (e.g. a `Message` or
  `UserMessage` table change).  There is a new Django feature added in
  [Django 1.10][migrations-non-atomic] that makes it possible to add
  `atomic=False` at the top of a `Migration` class and thus not have
  the entire migration in a transaction.  This should make it possible
  to use the batch update tools in `zerver/lib/migrate.py` (originally
  written to work with South) for doing larger database migrations.

* **Accessing code and models in RunPython migrations**. When writing
  a migration that includes custom python code (aka `RunPython`), you
  almost never want to import code from `zerver` or anywhere else in
  the codebase. If you imagine the process of upgrading a Zulip
  server, it goes as follows: first a server admin checks out a recent
  version of the code, and then runs any migrations that were added
  between the last time they upgraded and the current check out. Note
  that for each migration, this means the migration is run using the
  code in the server admin's check out, and not the code that was there at the
  time the migration was written. This can be a difference of
  thousands of commits for installations that are only upgraded
  occasionally. It is hard to reason about the effect of a code change
  on a migration that imported it so long ago, so we recommend just
  copying any code you're tempted to import into the migration file
  directly, and have a linter rule enforcing this.

  There is one special case where this doesn't work: you can't copy
  the definition of a model (like `Realm`) into a migration, and you
  can't import it from `zerver.models` for the reasons above. In this
  situation you should use Django's `apps.get_model` to get access to
  a model as it is at the time of a migration. Note that this will
  work for doing something like `Realm.objects.filter(..)`, but
  shouldn't be used for accessing `Realm.subdomain` or anything not
  related to the Django ORM.

* **Making large migrations work**.  Major migrations should have a
few properties:

  * **Unit tests**.  You'll want to carefully test these, so you might
    as well write some unit tests to verify the migration works
    correctly, rather than doing everything by hand.  This often saves
    a lot of time in re-testing the migration process as we make
    adjustments to the plan.
  * **Run in batches**.  Updating more than 1K-10K rows (depending on
    type) in a single transaction can lock up a database.  It's best
    to do lots of small batches, potentially with a brief sleep in
    between, so that we don't block other operations from finishing.
  * **Rerunnability/idempotency**.  Good migrations are ones where if
    operational concerns (e.g. it taking down the Zulip server for
    users) interfere with it finishing, it's easy to restart the
    migration without doing a bunch of hand investigation.  Ideally,
    the migration can even continue where it left off, without needing
    to redo work.
  * **Multi-step migrations**.  For really big migrations, one wants
  to split the transition into into several commits that are each
  individually correct, and can each be deployed independently:

    1. First, do a migration to add the new column to the Message table
      and start writing to that column (but don't use it for anything)
    2. Second, do a migration to copy values from the old column to
    the new column, to ensure that the two data stores agree.
    3. Third, a commit that stops writing to the old field.
    4. Any cleanup work, e.g. if the old field were a column, we'd do
       a migration to remove it entirely here.

    This multi-step process is how most migrations on large database
    tables are done in large-scale systems, since it ensures that the
    system can continue running happily during the migration.

[migrations-non-atomic]: https://docs.djangoproject.com/en/1.10/howto/writing-migrations/#non-atomic-migrations
