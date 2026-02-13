# Database concurrency

## select_for_update()

When a transaction does a read-then-write sequence where correctness depends on the
state it read, it needs a row lock to serialize that operation with other
writers. Without a lock, another transaction can commit between the read and
write, making the transaction have stale information. Two requests/workers can
then apply conflicting updates.

Django exposes a way to control the appropriate row locks via
[`QuerySet.select_for_update()`][django-select-for-update-doc]. This produces
either `SELECT ... FOR NO KEY UPDATE` or `SELECT ... FOR UPDATE` queries,
depending on the `no_key` boolean argument passed to `select_for_update()`. The
key decision at each call site is choosing the appropriate lock strength.

[django-select-for-update-doc]: https://docs.djangoproject.com/en/5.0/ref/models/querysets/#select-for-update

### What select_for_update() does

`select_for_update()` issues a `SELECT ... FOR ...` query that locks the
selected rows until the surrounding transaction commits or rolls back. A
transaction trying to take a conflicting lock on those rows will block.
The behavior can be modified to either fail immediately if the lock can't be taken
or skip the rows we cannot lock, via the `nowait=True` and `skip_locked=True` arguments,
respectively.

This is the right tool for code paths where correctness depends on reading a
stable value and then writing based on that value in the same transaction.
This protection only works if other code paths that mutate the same data also
use appropriate row locks.

Because the lock lives for the duration of the transaction, we should keep the
`transaction.atomic()` block small once the lock is acquired.

As a project policy, Zulip requires an explicit `no_key=` kwarg on every
`select_for_update()` call, enforced by semgrep.

### Lock strengths (`no_key`)

Django's `select_for_update(no_key=...)` maps to PostgreSQL row-level locks:

- `no_key=True` takes a `FOR NO KEY UPDATE` lock.
- `no_key=False` takes a `FOR UPDATE` lock.

`FOR UPDATE` is stronger. In particular, it conflicts with the `FOR KEY SHARE` lock,
which PostgreSQL acquires for foreign-key checks when inserting/updating
referencing rows. Therefore, `FOR UPDATE` on a parent row will block inserts in other
tables that reference that row.

`FOR NO KEY UPDATE` still protects against concurrent writes to the locked row,
but does not block `FOR KEY SHARE`. This avoids unnecessary cross-table
contention and is usually the right default, unless the transaction has the possibility
of deleting some of the selected rows.

See [PostgreSQL's row-level lock documentation][postgres-row-level-lock-doc] for
further detail.

### Choosing `no_key=True` vs `no_key=False`

Use `no_key=True` when:

- You are updating fields other than FK-referenced key columns (in Zulip
  today, this is effectively just the row's primary key column).
- You are serializing access to prevent lost updates/races.
- The row itself will not be deleted and those key columns are not changing.

Use `no_key=False` when:

- You will delete the locked row (or call helper code that may delete it).
- You will change key columns that are referenced by foreign keys (as noted
  above, in Zulip today, this is just the row's primary key column).
- You intentionally need to block FK-reference creation to that row while the
  transaction is in progress.

If using `no_key=False`, add a short comment explaining why the stronger lock is
required.

### Example patterns

Typical update path (`no_key=True`):

```python
with transaction.atomic():
    row = Model.objects.select_for_update(no_key=True).get(id=row_id)
    row.some_number = row.some_number + 1
    row.save(update_fields=["some_number"])
```

Delete path (`no_key=False`):

```python
with transaction.atomic():
    row = Model.objects.select_for_update(no_key=False).get(id=row_id)
    maybe_delete_row(row)
```

When locking rows from a queryset with joins, use `of=("self",)` unless you
intentionally need to lock related tables too.

```python
rows = Message.objects.select_related(*Message.DEFAULT_SELECT_RELATED) \
    .select_for_update(of=("self",), no_key=True)
```

[postgres-row-level-lock-doc]: https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS
