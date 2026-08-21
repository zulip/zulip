# Schema migrations

Zulip uses the [standard Django system for doing schema
migrations](https://docs.djangoproject.com/en/5.0/topics/migrations/).
There is some example usage in the [new feature
tutorial](../tutorials/new-feature-tutorial.md).

This page documents the conventions and constraints that apply to
writing schema migrations for Zulip. Many of those constraints come
from how Zulip Cloud deploys, which is described in the next section
and which most of the rules below trace back to.

## How Zulip Cloud deploys migrations

> **A migration must be safe to apply with the previous release's
> application code still running, and the previous release's code
> must continue to work correctly against the new schema until
> production deploys.**

That rule follows from a few facts about how Zulip Cloud is
operated. Contributors writing migrations should internalize
these before writing anything.

- **Staging and production share a single database.** There is one
  PostgreSQL cluster. Staging is a separate set of application
  servers (running internal-testing traffic, not live customer
  traffic), but it points at the same database production uses.
- **Staging deploys first.** Migrations are applied when staging
  deploys, against the shared database. Production then deploys
  some time later — typically about half an hour, occasionally
  longer — running the new code against the already-migrated
  database.
- **During that window, production runs the previous release's code
  against the new schema.** Old code must continue to read, insert,
  and update successfully against the migrated database the whole
  time.
- **Staging runs migrations against production-scale data.** This
  is a real safety net: a migration that's too slow, holds locks for
  too long, or has any other operational problem will manifest at
  staging-deploy time, on the actual database. But because the
  database is shared, those problems are also a live production
  issue while they're happening. The bar is to design the migration
  correctly up front, not to discover problems on staging.
- **The deploy tooling can choose which commits go to staging and
  production independently.** This gives the deploy operator levers:
  hold a risky migration back from production for a bit, deploy a
  schema change ahead of the code that uses it, or skip a migration
  entirely. The cleanest version of this would be reverting a
  specific commit, but in practice migrations are not always split
  cleanly enough to make that easy, so we also use a stub-out /
  `migrate --fake` workflow described in
  [When a migration can't be online-safe](#when-a-migration-cant-be-online-safe).

This isn't only about the staging/production shared database.
Cloud's Django processes also restart in a rolling fashion at
deploy time, so even within a single deploy there's a window
during which some processes are running the old code and some
the new — and old and new code must both function against the
live schema. (Self-hosted deploys typically stop the server, run
migrations, and start it back up, so neither constraint applies
there — but Cloud inherits both.)

If you can't satisfy the rule above, the migration needs to be
deferred until the dependent code is in production; see [When a
migration can't be online-safe](#when-a-migration-cant-be-online-safe).

## The simple case

If your migration just reflects new fields you've added to
`zerver/models/*.py`, rebase your branch first, then run
`./manage.py makemigrations`, rename the generated file if
Django's auto-picked name is awkward, run `tools/provision` to
apply it locally, and commit with the migration file added.

For migrations that need custom Python to transform existing
data, see [Writing RunPython
migrations](#writing-runpython-migrations); for migrations on
large tables, see [Making large migrations
work](#making-large-migrations-work).

## Working with the migration graph

### Numbering conflicts across branches

If you've done your schema change in a branch, and meanwhile another
schema change has taken place, Django will now have two migrations
with the same number. There are two easy ways to fix this:

- If your migrations were automatically generated using `manage.py
makemigrations`, a good option is to just remove your migration and
  rerun the command after rebasing. Remember to `git rebase` to do
  this in the commit that changed `models/*.py` if you have a
  multi-commit branch.
- If you wrote code as part of preparing your migrations, or prefer
  this workflow, you can run `./tools/renumber-migrations`, which
  renumbers your migration(s) and fixes up the "dependencies"
  entries. It updates the working tree for you (you still need to
  `git add` the result).

`./tools/test-migrations` checks that the migration graph is
consistent with the current models and flags auto-named
migrations that should be renamed. It runs as part of `test-all`
and is the first thing to run when sorting out a numbering or
graph problem.

### Release branches

When a release branch needs a migration, but `main` already has new
migrations, the migration graph must fork. The migration should be
named and numbered in `main` to follow the usual sequence, but its
dependency should be set to the last migration that exists on the
release branch. This should be followed, on `main`, by a migration
which merges the two resulting tips; you can make such a merge with
`manage.py makemigrations --merge`. Structuring the fork this way
makes the migration safe to cherry-pick back into the stable release
branch. See Django's [Controlling the order of
migrations](https://docs.djangoproject.com/en/6.0/howto/writing-migrations/#controlling-the-order-of-migrations)
for the underlying `dependencies` / `run_before` mechanics, or
`zerver/migrations/0754_merge_20251014_1855.py` for an example of
the merge migration that joins the forked tips.

## Adding columns safely

The shared-database deploy model means that adding a column requires
some care: production's old code keeps running `INSERT` and `UPDATE`
statements against the table that don't list the new column.

### Always set a database default

Set `db_default=` (in addition to Django's `default=`) on any new
**non-nullable** column introduced via `AddField`. Without
`db_default`, PostgreSQL has no
fallback when old code's `INSERT` omits the column, and those
inserts will fail the `NOT NULL` constraint in production until
the new code is deployed. (For nullable columns this isn't a
concern — the column simply takes `NULL` for omitted inserts.)

```python
migrations.AddField(
    model_name="realmauditlog",
    name="scrubbed",
    field=models.BooleanField(db_default=False, default=False),
),
```

`default=` is the Django-level default used by ORM `.create()`,
`save()`, etc. when the new code runs; `db_default=` is the
PostgreSQL-level default that protects old code during the deploy
window. Both are needed.

### Per-row defaults: nullable, backfill, NOT NULL

Some new columns can't take a static default — for example, a
foreign key to a per-realm `NamedUserGroup`, or a value derived
from other columns on the same row. The standard shape for these
is three migrations:

1. **Add the column nullable** (`AddField(..., null=True)`). Old
   code is unaffected because it doesn't reference the column;
   any inserts (from old or new code) leave the column `NULL`.
2. **Backfill the pre-existing rows** in batches with a
   `RunPython` data migration that has `atomic = False`. See
   [Making large migrations work](#making-large-migrations-work)
   for the batching patterns.
3. **Flip the column to `NOT NULL`** with an `AlterField` that
   redeclares the field without `null=True` (Django defaults
   non-`null` field types to `NOT NULL`, so an explicit
   `null=False` is rarely written).

A canonical recent example is the trio
`0710_realm_topics_policy.py` →
`0711_set_default_value_for_realm_topics_policy.py` →
`0712_alter_realm_topics_policy.py`. Many of the per-stream and
per-realm group-permission settings follow this pattern as well.
Django's [Migrations that add unique
fields](https://docs.djangoproject.com/en/6.0/howto/writing-migrations/#migrations-that-add-unique-fields)
documents the same structural pattern.

For this sequence to be safe on the shared database, two
properties of the application code are non-negotiable:

- **The code that populates the column must be in production before
  the `NOT NULL` migration runs.** It must populate the column on
  every code path that creates a row. If any path is missed,
  production will create a `NULL` row and the constraint will reject
  the insert, failing the request with a 500.
- **The code that reads the column must tolerate `NULL` until the
  backfill is complete.** Almost always this means simply not
  reading the column until step 3 lands.

These are properties of the application code change, not of the
migrations themselves. Your job as a contributor is to write the
code so these properties hold, audit every relevant code path,
and make the backfill idempotent (`filter(column=None)`) so it's
safe to re-run.

The application code and all three migrations typically ship in
the same PR. The deploy operator is responsible for sequencing
them across deploy cycles so that the populating code reaches
production before the `NOT NULL` migration is applied to the
shared database — choosing which commits to ship to staging vs.
production, deferring the `NOT NULL` migration if needed, or
using the [stub-out / `migrate --fake`
workflow](#when-a-migration-cant-be-online-safe). Call this
sequence out in the PR description so the operator knows to
handle it.

## Indexes

### Adding indexes

Django's regular `AddIndex` operation (corresponding to `CREATE
INDEX` in SQL) takes a lock that blocks writes to the affected
table for the duration of the build. On large tables (`Message`,
`UserMessage`, `Subscription`, `RealmAuditLog`, etc.) that lock
can last long enough to affect production. Use
`MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY= True` and
`add_index` (from `zerver.lib.migrate`)
for any index on those tables, and as a default for any index on a
table large enough that the lock would be noticeable.

For an index on plain table columns, `CREATE INDEX` populates
the index relation's own size/row statistics and the planner
can already estimate selectivity from existing column
statistics — no follow-up `ANALYZE` is needed. For **expression
indexes** (e.g., `Upper(subject)`), PostgreSQL only gathers
per-expression statistics in `pg_statistic` when `ANALYZE`
runs, so add a `RunSQL("ANALYZE zerver_<table>")` after the
`add_index` so the planner has the distribution info
it needs to use the new index.

### Renaming indexes

When the index naming scheme changes, prefer `RenameIndex` to
dropping and rebuilding (see
`0693_add_conditional_indexes_for_topic.py`, which also adds
expression indexes; note that it mistakenly omits the `ANALYZE`
that those would need).

### Dropping indexes

To drop an index `CONCURRENTLY` — for example, the auto-created
index on a foreign key whose `db_index` you're setting to
`False` — use
[SeparateDatabaseAndState](#separating-database-and-state).
Django's `AlterField(db_index=False)` issues a regular (locking)
`DROP INDEX`; the separate-state pattern lets you keep Django's
model tracking in sync while doing the actual drop concurrently.

## Constraints on large tables

Django's `AddConstraint` takes an `ACCESS EXCLUSIVE` lock on the
table and validates the constraint against every row before
returning, which can hold writes for a long time on a large
table. Standard Django doesn't expose the PostgreSQL features
that avoid this, so the patterns below all reach for `RunSQL` /
`RunPython` and use [SeparateDatabaseAndState](#separating-database-and-state)
to keep Django's model state in sync with what we did at the DB
level.

### `UNIQUE` constraints

Build a unique index `CONCURRENTLY`, then promote it to a table
constraint via `ALTER TABLE ... ADD CONSTRAINT ... UNIQUE USING
INDEX` (an instant metadata operation). See
`0794_alter_directmessagegroup_recipient_and_more.py` for the
canonical implementation, including the introspection-based
helper that handles the case where a previous run created the
index but crashed before promoting it. The state side is
whatever Django would have generated for the model change —
e.g., `AlterField` to `OneToOneField` if the uniqueness is on a
foreign key, or `AddConstraint(UniqueConstraint(...))` for a
non-foreign-key column.

### `CHECK` constraints

Declare the constraint in the model's `Meta.constraints` first
(without it, Django's `makemigrations --check` will see drift
when it compares state to model). Then write a single migration
that uses `SeparateDatabaseAndState` to do the DB work and
record the model-state change at the same time:

```python
migrations.SeparateDatabaseAndState(
    database_operations=[
        migrations.RunSQL(
            "ALTER TABLE zerver_foo ADD CONSTRAINT bar CHECK (...) NOT VALID;",
            reverse_sql="ALTER TABLE zerver_foo DROP CONSTRAINT bar;",
        ),
        migrations.RunSQL(
            "ALTER TABLE zerver_foo VALIDATE CONSTRAINT bar;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ],
    state_operations=[
        migrations.AddConstraint(
            model_name="foo",
            constraint=models.CheckConstraint(...),
        ),
    ],
)
```

The `NOT VALID` add records the constraint and enforces it for
new rows without scanning the existing table; `VALIDATE
CONSTRAINT` then scans without holding `ACCESS EXCLUSIVE`. Both
can run in a single (atomic) migration.

### Foreign key columns

Adding a foreign key column the default way triggers an `ACCESS
EXCLUSIVE` lock to validate the constraint. Avoid that with two
migrations:

1. **Add the column with `db_constraint=False`.** A plain
   `AddField` — Django emits the column-only DDL, no foreign key
   constraint, no `SeparateDatabaseAndState` wrapping needed:

   ```python
   migrations.AddField(
       model_name="foo",
       name="bar",
       field=models.ForeignKey(
           db_constraint=False,
           on_delete=models.CASCADE,
           to="zerver.bar",
       ),
   )
   ```

2. **Wrap the constraint creation in `SeparateDatabaseAndState`.**
   The DB side adds the constraint `NOT VALID` and validates it;
   the state side flips `db_constraint` back to its default
   (`True`) so Django's model tracking matches:

   ```python
   migrations.SeparateDatabaseAndState(
       database_operations=[
           migrations.RunSQL(
               "ALTER TABLE zerver_foo ADD CONSTRAINT zerver_foo_bar_id_fk "
               "FOREIGN KEY (bar_id) REFERENCES zerver_bar(id) NOT VALID;",
               reverse_sql="ALTER TABLE zerver_foo DROP CONSTRAINT zerver_foo_bar_id_fk;",
           ),
           migrations.RunSQL(
               "ALTER TABLE zerver_foo VALIDATE CONSTRAINT zerver_foo_bar_id_fk;",
               reverse_sql=migrations.RunSQL.noop,
           ),
       ],
       state_operations=[
           migrations.AlterField(
               model_name="foo",
               name="bar",
               field=models.ForeignKey(
                   on_delete=models.CASCADE,
                   to="zerver.bar",
               ),
           ),
       ],
   )
   ```

## Writing RunPython migrations

A small data migration looks like this (adapted from
`0795_rename_old_twitter_profile_fields.py`):

```python
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def update_twitter_to_x(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    CustomProfileField = apps.get_model("zerver", "CustomProfileField")
    # Copied from zerver/models/custom_profile_fields.py
    EXTERNAL_ACCOUNT = 7

    CustomProfileField.objects.filter(
        name="Twitter", field_type=EXTERNAL_ACCOUNT, field_data=...
    ).update(name="X username", ...)


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0794_alter_directmessagegroup_recipient_and_more"),
    ]

    operations = [
        migrations.RunPython(
            update_twitter_to_x,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
```

The bulk `.filter(...).update(...)` is fine for a small table
like `CustomProfileField`; for migrations that touch a large
table, see [Making large migrations
work](#making-large-migrations-work).

### Hygiene rules

- **Use `apps.get_model("zerver", "Foo")` to access models.** A
  Zulip server admin runs migrations using whatever code they've
  checked out, which can be thousands of commits newer than the
  migration. Importing `Foo` from `zerver.models` would mean the
  migration sees a model definition that didn't exist when it was
  written. `apps.get_model` returns the model as the migration
  graph defines it at that point in time. This works for ORM
  operations like `Foo.objects.filter(...)`; it doesn't expose
  Python-only methods or properties, so don't reach for those.
- **Don't import other code from `zerver` either.** If you need a
  constant, an enum value, or a small helper, copy it into the
  migration file with a comment noting where it came from. A linter
  rule enforces this. The reason is the same as for models: the
  imported code may have changed beyond recognition by the time the
  migration runs on a self-hosted server.
- **Set `reverse_code=migrations.RunPython.noop`** on data migrations
  unless you have a real inverse to provide. This is the project
  convention; the alternative (Django's default when `reverse_code` is
  unset) is to mark the migration irreversible, which is rarely the
  right semantics for a data migration whose forward effect just
  rewrites or fills in rows. The rare RunPython migrations which are
  truly irreversible should leave `reverse_code` unset, with an
  explicit comment as to why.
- **Set `elidable=True`** on data migrations whose effect won't be
  needed once `squashmigrations` collapses old migrations.
- **Make the data migration idempotent.** A migration may be
  interrupted partway through (operator action, restart, network
  blip) and re-run from the beginning. Filter your queryset on the
  "not yet migrated" condition (`field=None`,
  `subject__iexact="(no topic)"`, etc.) so re-running is a no-op for
  rows already done.
- **Be defensive about settings that may be removed.** If your
  migration reads a Django setting whose value drives behavior, use
  `getattr(settings, "FOO", default)` so the migration still runs
  on a future codebase where the setting has been deleted (see
  `0743_realm_require_e2ee_push_notifications.py`).
- **Use `psycopg2.sql.SQL` / `Identifier` for table and column
  names** in any raw SQL — never string-format them. The
  migration may end up sharing helpers or being adapted later;
  building safe-by-construction SQL avoids introducing an
  injection vector.

### Automated testing

Zulip has support for writing automated tests for your database
migrations, using the `MigrationsTestCase` test class. This system
is inspired by [a great blog post][django-migration-test-blog-post]
on the subject.

We have integrated this system with our test framework so that if
you use the `use_db_models` decorator, you can use some helper
methods from `test_classes.py` and friends from inside the tests
(which is normally not possible in Django's migrations framework).

If you find yourself writing logic in a `RunPython` migration, we
highly recommend adding a test using this framework. We may end up
deleting the test later (they can get slow once they are many
migrations away from current), but it can help prevent disaster
where an incorrect migration messes up a database in a way that's
impossible to undo without going to backups.

[django-migration-test-blog-post]: https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/

### Pending trigger events when mixing schema and data changes

Mixing data changes (`RunPython`) and `ALTER TABLE` operations in a
single atomic migration can produce:

```text
django.db.utils.OperationalError: cannot ALTER TABLE "table_name" because it has pending trigger events
```

PostgreSQL prohibits schema changes if there are deferred trigger
events still pending. Django creates foreign-key constraints as
`DEFERRABLE INITIALLY DEFERRED` in PostgreSQL by default, so foreign
key constraint checks are queued until commit time. You cannot run
`ALTER TABLE` while those checks are still queued.

Resolve this by making the migration non-atomic, splitting it into
two migration files (recommended), or replacing the `RunPython`
logic with pure SQL.

## Making large migrations work

For migrations that touch many rows or hold locks for non-trivial
amounts of time, the goal is to keep individual lock durations
short and total wall-clock time bounded.

### Use `do_batch_update` when it fits

For straightforward bulk updates over an entire table —
set a column to a value or SQL expression on every row —
`zerver/lib/migrate.py`'s `do_batch_update` helper handles all
the iteration for you:

```python
from zerver.lib.migrate import do_batch_update

def update_is_channel_message(apps, schema_editor):
    Message = apps.get_model("zerver", "Message")
    with connection.cursor() as cursor:
        do_batch_update(
            cursor,
            Message._meta.db_table,
            [SQL("is_channel_message = (SELECT type = 2 ...)")],
        )

class Migration(migrations.Migration):
    atomic = False
    operations = [
        migrations.RunPython(update_is_channel_message, ...),
    ]
```

It computes the table's `MIN(id)` and `MAX(id)`, walks the table
in batches of 10000 by default, sleeps briefly between batches,
and extends the upper bound if new rows have arrived during the
run, so rows inserted concurrently aren't missed. Reach for it first; only write a
hand-rolled loop when the helper doesn't fit (per-realm
scoping, multi-step batches, or a non-`UPDATE` operation). See
`0691_backfill_message_is_channel_message.py` for a complete
example.

### Push logic into the database

A `RunPython` loop that reads rows in Python, computes a value,
and writes them back is almost always slower and lock-heavier
than a single SQL `UPDATE ... FROM (subquery)` per chunk. When
you can, express the migration as SQL — see
`0705_stream_subscriber_count_data_migration.py`, which uses one
`UPDATE ... FROM (subquery)` per realm to backfill stream
subscriber counts.

### Iterate with `.iterator()`

Django querysets cache their entire result set in memory by
default. Whenever a migration loops over a queryset that could be
large, use `.iterator()` to stream rows one at a time:

```python
for realm in Realm.objects.all().iterator():
    ...
```

This applies to any per-row processing — emoji files, audit log
entries, individual realms — not just to walking large tables.

### Writing a hand-rolled batch loop

When `do_batch_update` doesn't fit, write the batch loop
yourself. The skeleton:

```python
class Migration(migrations.Migration):
    atomic = False
    ...

def backfill(apps, schema_editor):
    while lower_bound <= max_id:
        print(f"Processing {lower_bound}/{max_id}...")
        with transaction.atomic():
            Stream.objects.filter(
                id__range=(lower_bound, lower_bound + BATCH_SIZE - 1),
                ...
            ).update(...)
        lower_bound += BATCH_SIZE
```

See `0765_set_default_can_create_topic_group.py` for a complete
example. The considerations:

- **Set [`atomic = False`](https://docs.djangoproject.com/en/6.0/howto/writing-migrations/#non-atomic-migrations)
  on the migration class** and wrap each batch in its own
  `transaction.atomic()`. Django's default per-migration
  transaction would hold row locks for the entire
  run; per-batch commits release locks between iterations.
- **Batch by ID range**, not `OFFSET`. `id__range=(lower, upper)`
  is O(batch size) per page; `OFFSET` makes each subsequent page
  skip more rows. ID ranges aren't dense (gaps from deletes,
  scattered filter matches), so the number of rows touched per
  batch will vary, sometimes considerably — that's not an issue;
  the goal is to bound how many rows a single transaction holds
  locks on, not to do equal-sized chunks of work.
- **For tables with `realm_id`, iterate per realm.** Processing
  one realm at a time keeps each transaction's lock footprint
  scoped to that realm and limits the blast radius of any single
  batch. See `0696_rename_no_topic_to_empty_string_topic.py` and
  `0782_delete_unused_anonymous_groups.py`.
- **A few thousand rows is a reasonable batch size**; tune based
  on per-row cost. If a batch takes more than a few seconds,
  either the batch is too big or the work belongs in SQL.

### Separating database and state

Occasionally the SQL Django would auto-generate for a model
change isn't the SQL you want to run — most often because
Django's standard operations don't have a concurrent variant
(e.g., `AlterField(db_index=False)` issues a locking `DROP
INDEX`). `SeparateDatabaseAndState` lets you tell Django to
update its model-state tracking using one set of operations
while you actually execute a different set against the database:

```python
migrations.SeparateDatabaseAndState(
    database_operations=[migrations.RunPython(...)],
    state_operations=[migrations.AlterField(...)],
)
```

The two sides end up in agreement on the schema — Django's view
matches the database — but the DB-side change runs as your
custom SQL or `RunPython` rather than as Django's auto-generated
DDL. See
`0791_alter_archivedusermessage_user_profile_and_more.py` for a
recent example: the state side does `AlterField(db_index=False)`
on a foreign key, while the database side runs `DROP INDEX
CONCURRENTLY` on the underlying index.

### Multi-step rollouts: replacing a column

This pattern is only needed because Zulip Cloud migrates online —
a stop-the-server-and-migrate self-hosted upgrade can rename or
swap a column in a single migration without coordination. For a
column replacement on a large table on Cloud, split the
transition across multiple deploys that are each individually
correct against the previous deploy's code:

1. Add the new column (with `db_default`) and start writing to it
   in addition to the old column. Don't read from it yet.
2. Backfill the new column from the old column.
3. Confirm that the two columns contain identical data.
4. Switch readers to the new column. Stop writing to the old
   column.
5. Drop the old column.

Each deploy is safe against the previous deploy's running code.

## When a migration can't be online-safe

Sometimes a migration is genuinely incompatible with the old code
that will be running against the database during the deploy
window. The common cases are:

- **Dropping or renaming a column, table, or model that the
  previous release's code still references.** Old code's queries
  point at a schema element that no longer exists, so they fail
  the moment the migration applies.
- **A schema reshape where the intermediate state can't be read
  correctly by either the old or new code.** For example,
  restructuring a many-to-many relationship (Django's
  [worked example](https://docs.djangoproject.com/en/6.0/howto/writing-migrations/#changing-a-manytomanyfield-to-use-a-through-model)
  for swapping in a `through` model is a useful reference), or
  splitting one column's data across two new columns where the
  previous release expects the original column to be authoritative.

Migrations like these can't simply land on `main` and ship: applying
them to the shared database while production still runs the old
code would break production. The deploy operator handles them with
a stub-out / `migrate --fake` workflow:

1. The migration is committed to `main` and runs in dev and CI as
   normal.
2. In Cloud's internal deploy branch, the migration is replaced
   with a stub (a no-op) until the dependent code has reached
   production.
3. Deploy the new code to production.
4. Run `manage.py migrate --fake zerver <previous_migration>` to mark
   the stub as unapplied.
5. Restore the real migration.
6. Run `manage.py migrate zerver <target_migration>` to apply it for
   real.
7. Run `manage.py migrate --fake zerver <last_migration>` to move
   the migration state back to the tip.

If you write a migration that needs this treatment, **call it out
explicitly in the commit** so the operators are aware when reviewing
the pending migrations for a deploy.

The stub-out workflow exists because migrations are not always
split out from the application code that depends on them in
current practice. If they were each in their own commit — schema
change, backfill, and `NOT NULL` flip standalone — the operator
could revert or reorder a single commit instead of editing
migration files in place. For multi-step migrations where you
anticipate the operator may need to defer pieces, keeping each
migration in its own commit is worth the extra discipline.

## Local schema rebuilds

If you follow the processes described above, `tools/provision` and
`tools/test-backend` should detect any changes to the declared
migrations and run migrations on (`./manage.py migrate`) or rebuild
the relevant database automatically as appropriate.

Notably, both `manage.py migrate` (`git grep post_migrate.connect`
for details) and restarting `tools/run-dev` will flush `memcached`,
so you shouldn't have to worry about cached objects from a previous
database schema.

While developing migrations, you may accidentally corrupt your
databases while debugging your new code. You can always rebuild
these databases from scratch:

- Use `tools/rebuild-test-database` to rebuild the database used
  for `test-backend` and other automated tests.
- Use `tools/rebuild-dev-database` to rebuild the database used in
  [manual testing](../development/using.md).
