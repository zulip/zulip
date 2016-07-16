# Renumbering Migrations
When you rebase your development branch off of
a newer copy of master, and your branch contains
new database migrations, you can occasionally get
thrown off by conflicting migrations that are
new in master.

To help you understand how to deal with these
conflicts, I am about narrate an exercise
where I bring my development branch called
showell-topic up to date with master.

In this example,
there is a migration on master called
`0024_realm_allow_message_editing.py`, and
that was the most recent migration at the
time I started working on my branch.  In
my branch I created migrations 0025 and 0026,
but then meanwhile on master somebody else
created their own migration 0025.

Anyway, on with the details...

First, I go to showell-topic and run tests to
make sure that I'm starting with a clean, albeit
out-of-date, dev branch:

```
showell@Steves-MBP ~/zulip (showell-approximate) $ git checkout showell-topic
Switched to branch 'showell-topic'

showell@Steves-MBP ~/zulip (showell-topic) $ git status
# On branch showell-topic
nothing to commit, working directory clean

(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:/srv/zulip$ ./tools/test-backend
<output skipped>
DONE!
```

Next, I fetch changes from upstream:

```
showell@Steves-MBP ~/zulip (showell-topic) $ git checkout master
Switched to branch 'master'

showell@Steves-MBP ~/zulip (master) $ git fetch upstream

showell@Steves-MBP ~/zulip (master) $ git merge upstream/master
Updating 2967341..09754c9
Fast-forward
<etc.>
```

Then I go back to showell-topic:

```
showell@Steves-MBP ~/zulip (master) $ git checkout showell-topic
Switched to branch 'showell-topic'
```

You may want to make note of your HEAD commit on your branch
before you start rebasing, in case you need to start over, or
do like I do and rely on being able to find it via github.  I'm
not showing the details of that, since people have different
styles for managing botched rebases.

Anyway, I rebase to master as follows:

```
showell@Steves-MBP ~/zulip (showell-topic) $ git rebase -i master
Successfully rebased and updated refs/heads/showell-topic.
```

Note that my rebase was conflict-free from git's point of view,
but I still need to run the tests to make sure there weren't any
semantic conflicts with the new changes from master:

```
(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:/srv/zulip$ ./tools/test-backend

<output skipped>

  File "/srv/zulip-venv-cache/ad3a375e95a56d911510d7edba7e17280d227bc7/zulip-venv/local/lib/python2.7/site-packages/django/core/management/commands/migrate.py", line 105, in handle
    "'python manage.py makemigrations --merge'" % name_str
django.core.management.base.CommandError: Conflicting migrations detected (0026_topics_backfill, 0025_realm_message_content_edit_limit in zerver).
To fix them run 'python manage.py makemigrations --merge'

<output skipped>

  File "/srv/zulip/zerver/lib/db.py", line 33, in execute
    return wrapper_execute(self, super(TimeTrackingCursor, self).execute, query, vars)
  File "/srv/zulip/zerver/lib/db.py", line 20, in wrapper_execute
    return action(sql, params)
django.db.utils.ProgrammingError: relation "zerver_realmfilter" does not exist
LINE 1: ...n", "zerver_realmfilter"."url_format_string" FROM "zerver_re...
```

The above traceback is fairly noisy, but it's pretty apparent that
I have migrations that are out of order.  More precisely, my 0025 migration
points to 0024 as its dependency, where it really should point to the
other 0025 as its dependency, and I need to renumber my migrations to
0026 and 0027.

Let's take a peek at the migrations directory:

```
showell@Steves-MBP ~/zulip (showell-topic) $ ls -r zerver/migrations/*.py | head -6
zerver/migrations/__init__.py
zerver/migrations/0026_topics_backfill.py
zerver/migrations/0025_realm_message_content_edit_limit.py
zerver/migrations/0025_add_topic_table.py
zerver/migrations/0024_realm_allow_message_editing.py
zerver/migrations/0023_userprofile_default_language.py
```

We have two different 0025 migrations that both depend on 0024:

```
showell@Steves-MBP ~/zulip (showell-topic) $ grep -B 1 0024 zerver/migrations/*.py
zerver/migrations/0025_add_topic_table.py-    dependencies = [
zerver/migrations/0025_add_topic_table.py:        ('zerver', '0024_realm_allow_message_editing'),
--
zerver/migrations/0025_realm_message_content_edit_limit.py-    dependencies = [
zerver/migrations/0025_realm_message_content_edit_limit.py:        ('zerver', '0024_realm_allow_message_editing'),
```

I will now start the process of renaming `0025_add_topic_table.py` to
be `0026_add_topic_table.py` and having it depend on
`0025_realm_message_content_edit_limit`.  Before I start, I want to
know which of my commits created my 0025 migration:

```
showell@Steves-MBP ~/zulip (showell-topic) $ git log --pretty=oneline zerver/migrations/0025_add_topic_table.py
d859e6ffc165e822cec39152a5814ca7ce94d172 Add Topic and Message.topic to models
```

Here is the transcript, and hopefully what I did inside of vim is apparent
from the diff:

```
showell@Steves-MBP ~/zulip (showell-topic) $ cd zerver/migrations/
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic) $ git mv 0025_add_topic_table.py 0026_add_topic_table.py
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic +) $ vim 0026_add_topic_table.py
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic *+) $ git diff
diff --git a/zerver/migrations/0026_add_topic_table.py b/zerver/migrations/0026_add_topic_table.py
index 2c8c07a..43351eb 100644
--- a/zerver/migrations/0026_add_topic_table.py
+++ b/zerver/migrations/0026_add_topic_table.py
@@ -8,7 +8,7 @@ import zerver.lib.str_utils
 class Migration(migrations.Migration):

     dependencies = [
-        ('zerver', '0024_realm_allow_message_editing'),
+        ('zerver', '0025_realm_message_content_edit_limit'),
     ]

     operations = [
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic *+) $ git commit -am 'temp rename migration'
[showell-topic 45cf5e9] temp rename migration
 1 file changed, 1 insertion(+), 1 deletion(-)
 rename zerver/migrations/{0025_add_topic_table.py => 0026_add_topic_table.py} (93%)
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic) $ git status
# On branch showell-topic
nothing to commit, working directory clean
```

Next, I want to rewrite the history of my branch.  When I'm in the
interactive rebase (not shown), I need to make the temp commit be a
"fix" for the original commit that I noted above:

```
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic) $ git rebase -i master
[detached HEAD c1f2e69] Add Topic and Message.topic to models
 2 files changed, 38 insertions(+)
 create mode 100644 zerver/migrations/0026_add_topic_table.py
Successfully rebased and updated refs/heads/showell-topic.
```

I did this to verify that I rebased correctly:

```
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic) $ git log 0026_add_topic_table.py
commit c1f2e69e716beb4031c628fe2189b49f04770d03
Author: Steve Howell <showell30@yahoo.com>
Date:   Thu Jul 14 13:26:15 2016 -0700

    Add Topic and Message.topic to models
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic) $ git show c1f2e69e716beb4031c628fe2189b49f04770d03
<not shown here>
```

Next, I follow a very similar process for my second migration-related
commit on my branch:


```
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic) $ git log --pretty=oneline 0026_topics_backfill.py
ba43e1ffb072f4e6a66ffb5c4030ff3a17d53792 (unfinished) stub commit for topic backfill
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic) $ git mv 0026_topics_backfill.py 0027_topics_backfill.py
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic +) $ vim 0027_topics_backfill.py
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic *+) $ git diff
diff --git a/zerver/migrations/0027_topics_backfill.py b/zerver/migrations/0027_topics_backfill.py
index 766b075..05ea2bb 100644
--- a/zerver/migrations/0027_topics_backfill.py
+++ b/zerver/migrations/0027_topics_backfill.py
@@ -8,7 +8,7 @@ import zerver.lib.str_utils
 class Migration(migrations.Migration):

     dependencies = [
-        ('zerver', '0025_add_topic_table'),
+        ('zerver', '0026_add_topic_table'),
     ]

     operations = [
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic *+) $ git commit -am 'temp rename migration'
[showell-topic 02ef15b] temp rename migration
 1 file changed, 1 insertion(+), 1 deletion(-)
 rename zerver/migrations/{0026_topics_backfill.py => 0027_topics_backfill.py} (90%)
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic) $ git rebase -i master
[detached HEAD 8022839] (unfinished) stub commit for topic backfill
 1 file changed, 20 insertions(+)
 create mode 100644 zerver/migrations/0027_topics_backfill.py
Successfully rebased and updated refs/heads/showell-topic.
```

My rebase looked something like this after I edited the commits:

```
  1 pick eee291d Add subject_topic_awareness() test helper.
  2 pick c1f2e69 Add Topic and Message.topic to models
  3 pick 46c04b5 Call new update_topic() in pre_save_message().
  4 pick df20dc8 Write to Topic table for topic edits.
  5 pick ba43e1f (unfinished) stub commit for topic backfill
  6 f 02ef15b temp rename migration
  7 pick b8e93d2 Add CATCH_TOPIC_MIGRATION_BUGS.
  8 pick 644ccae Have get_context_for_message use topic_id.
  9 pick 6303f5b Have update_message_flags user topic_id.
 10 pick 9f9da5a Have narrowing searches use topic id.
 11 pick 0b37ef7 Assert that new_topic=True obliterates message.subject
 12 pick dff8eee Use new_topics=True in test_bulk_message_fetching().
 13 pick bc377a0 Use topic_id when propagating message edits.
 14 pick 11fde9c Have message cache use Topic table (and more...).
 15 pick 518649b Use topic_name() in to_log_dict().
 16
 17 # Rebase 09754c9..02ef15b onto 09754c9
 18 #
 19 # Commands:
 20 #  p, pick = use commit
 21 #  r, reword = use commit, but edit the commit message
 22 #  e, edit = use commit, but stop for amending
 23 #  s, squash = use commit, but meld into previous commit
 24 #  f, fixup = like "squash", but discard this commit's log message
 25 #  x, exec = run command (the rest of the line) using shell
```

I double check that everything went fine:

```
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic) $ git log 0027_topics_backfill.py
commit 8022839f9168e643ae08365bfb40f1de2e64d426
Author: Steve Howell <showell30@yahoo.com>
Date:   Thu Jul 14 15:51:06 2016 -0700

    (unfinished) stub commit for topic backfill
showell@Steves-MBP ~/zulip/zerver/migrations (showell-topic) $ git show 8022839f9168e643ae08365bfb40f1de2e64d426
<not shown here>
```

And then I run the tests and cross my fingers!!!:

```
(zulip-venv)vagrant@vagrant-ubuntu-trusty-64:/srv/zulip$ ./tools/test-backend
<output skipped>
  Applying zerver.0023_userprofile_default_language... OK
  Applying zerver.0024_realm_allow_message_editing... OK
  Applying zerver.0025_realm_message_content_edit_limit... OK
  Applying zerver.0026_add_topic_table... OK
  Applying zerver.0027_topics_backfill... OK
  Applying zilencer.0001_initial... OK
Successfully populated test database.
DROP DATABASE
CREATE DATABASE
Running zerver.tests.test_auth_backends.AuthBackendTest.test_devauth_backend
Running zerver.tests.test_auth_backends.AuthBackendTest.test_dummy_backend
Running zerver.tests.test_auth_backends.AuthBackendTest.test_email_auth_backend
<output skipped>
FAILED!
```

Ugh, my tests still fail due to some non-migration-related changes on master.
The good news, however, is that my migrations are cleaned up.

So I've shown you the excruciating details of fixing up migrations
in a complicated branch, but let's step back and look at the big
picture.  You need to get these things right:

- Rename the migrations on your branch.
- Fix their dependencies.
- Rewrite your git history so that it appears like you never branched off an old copy of master.

The hardest part of the process will probably be cleaning up your git history.
