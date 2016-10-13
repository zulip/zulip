# Schema Migrations

Zulip uses the [standard Django system for doing schema
migrations](https://docs.djangoproject.com/en/1.8/topics/migrations/).
There is some example usage in the [new feature
tutorial](new-feature-tutorial.html).

This page documents some important issues related to writing schema
migrations.

* **Large tables**: For large tables like Message and UserMessage, you
  want to take precautions when adding columns to the table,
  performing data backfills, or building indexes. We have a
  `zerver/lib/migrate.py` library to help with adding columns and
  backfilling data. For building indexes on these tables, we should do
  this using SQL with postgres's CONCURRENTLY keyword.

* **Numbering conflicts across branches**: If you've done your schema
  change in a branch, and meanwhile another schema change has taken
  place, Django will now have two migrations with the same number. To
  fix this, you need to renumber your migration(s), fix up
  the "dependencies" entries in your migration(s), and rewrite your
  git history as needed.  There is a tutorial
  [here](migration-renumbering.html) that walks you though that
  process.
