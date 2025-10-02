# Schema migrations

Zulip uses the [standard Django system for doing schema
migrations](https://docs.djangoproject.com/en/5.0/topics/migrations/).
There is some example usage in the [new feature
tutorial](../tutorials/new-feature-tutorial.md).

This page documents some important issues related to writing schema
migrations.

- If your database migration is just to reflect new fields in
  `models/*.py`, you'll typically want to just:
  - Rebase your branch before you start (this may save work later).
  - Update the model class definitions in `zerver/models/*.py`.
  - Run `./manage.py makemigrations` to generate a migration file
  - Rename the migration file to have a descriptive name if Django
    generated used a date-based name like `0089_auto_20170710_1353.py`
    (which happens when the changes are to multiple models and Django).
  - `git add` the new migration file
  - Run `tools/provision` to update your local database to apply the
    migrations.
  - Commit your changes.
- For more complicated migrations where you need to run custom Python
  code as part of the migration, it's best to read past migrations to
  understand how to write them well.
  `git grep RunPython zerver/migrations/02*` will find many good
  examples. Before writing migrations of this form, you should read
  Django's docs and the sections below.
- **Numbering conflicts across branches**: If you've done your schema
  change in a branch, and meanwhile another schema change has taken
  place, Django will now have two migrations with the same
  number. There are two easy way to fix this:
  - If your migrations were automatically generated using
    `manage.py makemigrations`, a good option is to just remove your
    migration and rerun the command after rebasing. Remember to
    `git rebase` to do this in the commit that changed `models/*.py`
    if you have a multi-commit branch.
  - If you wrote code as part of preparing your migrations, or prefer
    this workflow, you can use run `./tools/renumber-migrations`,
    which renumbers your migration(s) and fixes up the "dependencies"
    entries in your migration(s). The tool could use a bit of work to
    prompt unnecessarily less, but it will update the working tree for
    you automatically (you still need to do all the `git add`
    commands, etc.).
- **Release branches**: When a release branch needs a migration, but
  `main` already has new migrations, the migration graph must fork.
  The migration should be named and numbered in `main` to follow in
  usual sequence, but its dependency should be set to the last
  migration that exists on the release branch. This should be
  followed, on `main`, by a migration which merges the two resulting
  tips; you can make such a merge with `manage.py makemigrations --merge`.
- **Large tables**: For our very largest tables (e.g., Message and
  UserMessage), we often need to take precautions when adding columns
  to the table, performing data backfills, or building indexes. We
  have a `zerver/lib/migrate.py` library to help with adding columns
  and backfilling data.
- **Adding indexes**. Django's regular `AddIndex` operation (corresponding
  to `CREATE INDEX` in SQL) locks writes to the affected table. This can be
  problematic when dealing with larger tables in particular and we've
  generally preferred to use `AddIndexConcurrently` (corresponding to
  `CREATE INDEX CONCURRENTLY`) to allow the index to be built while
  the server is active.
- **Atomicity**. By default, each Django migration is run atomically
  inside a transaction. This can be problematic if one wants to do
  something in a migration that touches a lot of data and would best
  be done in batches of, for example, 1000 objects (e.g., a `Message` or
  `UserMessage` table change). There is a [useful Django
  feature][migrations-non-atomic] that makes it possible to add
  `atomic=False` at the top of a `Migration` class and thus not have
  the entire migration in a transaction. This should make it possible
  to use the batch update tools in `zerver/lib/migrate.py` (originally
  written to work with South) for doing larger database migrations.
- **No-op migrations**. Django detects model changes that does not
  necessarily lead to a schema change in the database.
  For example, field validators are a part of the Django ORM, but they
  are not stored in the database. When removing such validators from
  an existing model, nothing gets dropped from the database, but Django
  would still generate a migration for that. We prefer to avoid adding
  this kind of no-op migrations. Instead of generating a new migration,
  you'll want to modify the latest migration affecting the field.

- **Accessing code and models in RunPython migrations**. When writing
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
  shouldn't be used for accessing properties like `Realm.subdomain` or
  anything not related to the Django ORM.

  Another important note is that making changes to the data in a table
  via `RunPython` code and `ALTER TABLE` operations within a single,
  atomic migration don't mix well. If you encounter an error such as

  ```text
  django.db.utils.OperationalError: cannot ALTER TABLE "table_name" because it has pending trigger events
  ```

  when testing the migration, the reason is:

  PostgreSQL prohibits schema changes (e.g., `ALTER TABLE`)
  if there are deferred trigger events still pending.
  Now most Zulip constraints are `DEFERRABLE INITIALLY DEFERRED` which means
  the constraint will not be checked until the transaction is committed,
  and You are not allowed to update, insert, alter or any other query
  that will modify the table without executing all pending triggers which would be
  constraint checking in this case.

  To resolve this, consider making the migration
  non-atomic, splitting it into two migration files (recommended), or replacing the
  `RunPython` logic with pure SQL (though this can generally be difficult).

- **Making large migrations work**. Major migrations should have a
  few properties:

  - **Unit tests**. You'll want to carefully test these, so you might
    as well write some unit tests to verify the migration works
    correctly, rather than doing everything by hand. This often saves
    a lot of time in re-testing the migration process as we make
    adjustments to the plan.
  - **Run in batches**. Updating more than 1K-10K rows (depending on
    type) in a single transaction can lock up a database. It's best
    to do lots of small batches, potentially with a brief sleep in
    between, so that we don't block other operations from finishing.
  - **Rerunnability/idempotency**. Good migrations are ones where if
    operational concerns (e.g., it taking down the Zulip server for
    users) interfere with it finishing, it's easy to restart the
    migration without doing a bunch of hand investigation. Ideally,
    the migration can even continue where it left off, without needing
    to redo work.
  - **Multi-step migrations**. For really big migrations, one wants
    to split the transition into several commits that are each
    individually correct, and can each be deployed independently:

    1. First, do a migration to add the new column to the Message table
       and start writing to that column (but don't use it for anything)
    2. Second, do a migration to copy values from the old column to
       the new column, to ensure that the two data stores agree.
    3. Third, a commit that stops writing to the old field.
    4. Any cleanup work, e.g., if the old field were a column, we'd do
       a migration to remove it entirely here.

    This multi-step process is how most migrations on large database
    tables are done in large-scale systems, since it ensures that the
    system can continue running happily during the migration.

## Automated testing for migrations

Zulip has support for writing automated tests for your database
migrations, using the `MigrationsTestCase` test class. This system is
inspired by [a great blog post][django-migration-test-blog-post] on
the subject.

We have integrated this system with our test framework so that if you
use the `use_db_models` decorator, you can use some helper methods
from `test_classes.py` and friends from inside the tests (which is
normally not possible in Django's migrations framework).

If you find yourself writing logic in a `RunPython` migration, we
highly recommend adding a test using this framework. We may end up
deleting the test later (they can get slow once they are many
migrations away from current), but it can help prevent disaster where
an incorrect migration messes up a database in a way that's impossible
to undo without going to backups.

[django-migration-test-blog-post]: https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
[migrations-non-atomic]: https://docs.djangoproject.com/en/5.0/howto/writing-migrations/#non-atomic-migrations

## Schema and initial data changes

If you follow the processes described above, `tools/provision` and
`tools/test-backend` should detect any changes to the declared
migrations and run migrations on (`./manage.py migrate`) or rebuild
the relevant database automatically as appropriate.

Notably, both `manage.py migrate` (`git grep post_migrate.connect` for
details) and restarting `tools/run-dev` will flush `memcached`, so you
shouldn't have to worry about cached objects from a previous database
schema.

While developing migrations, you may accidentally corrupt your
databases while debugging your new code. You can always rebuild these
databases from scratch:

- Use `tools/rebuild-test-database` to rebuild the database
  used for `test-backend` and other automated tests.

- Use `tools/rebuild-dev-database` to rebuild the database
  used in [manual testing](../development/using.md).
