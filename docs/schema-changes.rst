==============
Schema changes
==============

If you are making a change that requires a database schema upgrade,
there are a few extra things you need to keep in mind.

Using South for migrations
--------------------------

1. Discuss the change informally with your team.
#. Edit ``zerver/models.py`` for your particular class.

   * See notes below about keep\_default.

#. Run ``./manage.py schemamigration zerver --auto``

   * This will create the ``000#_***.py`` schema migration file in
     ``zerver/migrations``.

#. Read `Notes and Cautions`_ section below, as you may need to edit
   the migration. A common step here is setting keep\_default to True.
#. Do ``git add`` with your new migration.
#. Run ``./manage.py migrate zerver``.
#. Write supporting code or otherwise validate the DB change locally.
   TODO: Advice on testing schema changes?
#. Commit your changes:

   a. The migration must be in the same commit as the models.py changes.
   #. Include [schema] in the commit message.
   #. Include [manual] in the commit message if additional steps are
      required.

#. Before deploying your code fix, read the notes on `Deploying to
   staging`_.

Deploying to staging
--------------------

Always follow this process.

1. Schedule the migration for after hours.

#. For long-running migrations, double check that you use appropriate
   library helpers in ``migrate.py`` to ensure that changes happen in small
   batches that are committed frequently.

#. Announce that you are doing the migration to your team, to avoid
   simultaneous migrations and other outcomes of poor communication.

#. Do any administrative steps, such as increasing
   checkpoint\_segments.

#. Apply the migration in advance from staging, using commands similar
   to the following, where ``[your commit]`` is the commit that has your
   migration::

     cd ~/zulip
     git fetch
     cd /tmp
     git clone ~/zulip
     cd zulip
     git checkout [your commit]
     ./manage.py migrate zerver
     cd /tmp
     rm -Rf zulip

#. Undo any temporary administrative changes, such as increasing
   checkpoint\_segments.

Because staging and prod share a database, for most migrations, nothing
special needs to be done when deploying to prod since the shared
database schema will have already been updated, but in some cases some
code to properly initialize data structures may need to be run.

Migrating to a new schema
-------------------------

When doing a git pull and noticing a [schema] commit, you must manually
perform a schema upgrade: ``./manage.py migrate zerver``.
``generate-fixtures`` should automatically detect whether
the schema has changed and update things accordingly.

Notes and Cautions
------------------

**Large tables**
  For large tables like Message and UserMessage, you
  want to take precautions when adding columns to the table, performing
  data backfills, or building indexes. We have a ``migrate.py`` library to
  help with adding columns and backfilling data. For building indexes,
  we should do this outside of South using postgres's CONCURRENTLY
  keyword.

**Numbering conflicts across branches**
  If you've done your schema change in a branch, and meanwhile another
  schema change has taken place, South will now have two migrations with
  the same number. To fix this, delete the migration file that South
  generated, and re-run ``./manage.py schemamigration zerver --auto``.

**Avoid nullables**
  You generally no longer need a Nullable column
  to avoid problems with staging and prod not having the same models.
  See the next point about setting ``keep_default=True``.

**Use keep\_default**
  When adding a new column to an existing table,
  you almost always will want to set ``keep_default=True`` in the South
  migration ``db.add_column`` call. If you don't, everything will
  appear to work fine in testing and on staging, but once the schema
  migration is done, the pre-migration code running on prod will be
  unable to save new rows for that table (so e.g. if you were adding a
  new field to UserProfile, we'd be unable to create new users). The
  exception to this rule is when your field default is not a constant
  value. In this case, you'll need to do something special to either
  set a database-level default or use a Nullable field and a multi-step
  schema deploy process.

**Rebase pain**
  If you ever need to rebase a schema change past
  other schema changes made on other branches, in addition to
  renumbering your schema change, youalso need to be sure to regenerate
  at least the bottom part of your migration (which shows the current
  state of all the models) after rebasing; if you don't, then the next
  migration made after your migration is merged will incorrectly
  attempt to re-apply all the schema changes made in the migration you
  skipped. This can be potentially dangerous.

**Upstreaming**
  We recommend upstreaming schema changes as soon as possible to
  avoid schema numbering conflicts (see above).
