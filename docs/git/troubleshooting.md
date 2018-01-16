# Get and stay out of trouble

Git is a powerful yet complex version control system. Even for contributors
experienced at using version control, it can be confusing. The good news is
that nearly all Git actions add information to the Git database, rather than
removing it. As such, it's hard to make Git perform actions that you can't
undo. However, git can't undo what it doesn't know about, so it's a good
practice to frequently commit your changes and frequently push your commits to
your remote repository.

## Undo a merge commit

A merge commit is a special type of commit that has two parent commits. It's
created by Git when you merge one branch into another and the last commit on
your current branch is not a direct ancestor of the branch you are trying to
merge in. This happens quite often in a busy project like Zulip where there are
many contributors because upstream/zulip will have new commits while you're
working on a feature or bugfix. In order for Git to merge your changes and the
changes that have occurred on zulip/upstream since you first started your work,
it must perform a three-way merge and create a merge commit.

Merge commits aren't bad, however, Zulip doesn't use them. Instead Zulip uses a
forked-repo, rebase-oriented workflow.

A merge commit is usually created when you've run `git pull` or `git merge`.
You'll know you're creating a merge commit if you're prompted for a commit
message and the default is something like this:

```
Merge branch 'master' of https://github.com/zulip/zulip

# Please enter a commit message to explain why this merge is necessary,
# especially if it merges an updated upstream into a topic branch.
#
# Lines starting with '#' will be ignored, and an empty message aborts
# the commit.
```

And the first entry for `git log` will show something like:

```
commit e5f8211a565a5a5448b93e98ed56415255546f94
Merge: 13bea0e e0c10ed
Author: Christie Koehler <ck@christi3k.net>
Date:   Mon Oct 10 13:25:51 2016 -0700

    Merge branch 'master' of https://github.com/zulip/zulip
```

Some graphical Git clients may also create merge commits.

To undo a merge commit, first run `git reflog` to identify the commit you want
to roll back to:

```
$ git reflog

e5f8211 HEAD@{0}: pull upstream master: Merge made by the 'recursive' strategy.
13bea0e HEAD@{1}: commit: test commit for docs.
```

Reflog output will be long. The most recent git refs will be listed at the top.
In the example above `e5f8211 HEAD@{0}:` is the merge commit made automatically
by `git pull` and `13bea0e HEAD@{1}:` is the last commit I made before running
`git pull`, the commit that I want to rollback to.

Once you'd identified the ref you want to revert to, you can do so with [git
reset][gitbook-reset]:

```
$ git reset --hard 13bea0e
HEAD is now at 13bea0e test commit for docs.
```

**Important:** `git reset --hard <commit>` will discard all changes in your
working directory and index since the commit you're resetting to with
*<commit>*. *This is the main way you can lose work in Git*. If you need to
keep any changes that are in your working directory or that you have committed,
use `git reset --merge <commit>` instead.

You can also use the relative reflog `HEAD@{1}` instead of the commit hash,
just keep in mind that this changes as you run git commands.

Now when you look at the output of `git reflog`, you should see that the tip of your branch points to your
last commit `13bea0e` before the merge:

```
$ git reflog

13bea0e HEAD@{2}: reset: moving to HEAD@{1}
e5f8211 HEAD@{3}: pull upstream master: Merge made by the 'recursive' strategy.
13bea0e HEAD@{4}: commit: test commit for docs.
```

And the first entry `git log` shows is this:

```
commit 13bea0e40197b1670e927a9eb05aaf50df9e8277
Author: Christie Koehler <ck@christi3k.net>
Date:   Mon Oct 10 13:25:38 2016 -0700

    test commit for docs.
```

## Restore a lost commit

We've mentioned you can use `git reset --hard` to rollback to a previous
commit. What if you run `git reset --hard` and then realize you actually need
one or more of the commits you just discarded? No problem, you can restore them
with `git cherry-pick` ([docs][gitbook-git-cherry-pick]).

For example, let's say you just committed "some work" and your `git log` looks
like this:

```
* 67aea58 (HEAD -> master) some work
* 13bea0e test commit for docs.
```

You then mistakenly run `git reset --hard 13bea0e`:

```
$ git reset --hard 13bea0e
HEAD is now at 13bea0e test commit for docs.

$ git log
* 13bea0e (HEAD -> master) test commit for docs.
```

And then realize you actually needed to keep commit 67aea58. First, use `git
reflog` to confirm that commit you want to restore and then run `git
cherry-pick <commit>`:

```
$ git reflog
13bea0e HEAD@{0}: reset: moving to 13bea0e
67aea58 HEAD@{1}: commit: some work

$ git cherry-pick 67aea58
 [master 67aea58] some work
 Date: Thu Oct 13 11:51:19 2016 -0700
 1 file changed, 1 insertion(+)
 create mode 100644 test4.txt
```

## Recover from a git rebase failure

One situation in which `git rebase` will fail and require you to intervene is
when your change, which git will try to re-apply on top of new commits from
which ever branch you are rebasing on top of, is to code that has been changed
by those new commits.

For example, while I'm working on a file, another contributor makes a change to
that file, submits a pull request and has their code merged into master.
Usually this is not a problem, but in this case the other contributor made a
change to a part of the file I also want to change. When I try to bring my
branch up to date with `git fetch` and then `git rebase upstream/master`, I see
the following:

```
First, rewinding head to replay your work on top of it...
Applying: test change for docs
Using index info to reconstruct a base tree...
M    README.md
Falling back to patching base and 3-way merge...
Auto-merging README.md
CONFLICT (content): Merge conflict in README.md
error: Failed to merge in the changes.
Patch failed at 0001 test change for docs
The copy of the patch that failed is found in: .git/rebase-apply/patch

When you have resolved this problem, run "git rebase --continue".
If you prefer to skip this patch, run "git rebase --skip" instead.
To check out the original branch and stop rebasing, run "git rebase --abort".
```

This message tells me that Git was not able to apply my changes to README.md
after bringing in the new commits from upstream/master.

Running `git status` also gives me some information:

```
rebase in progress; onto 5ae56e6
You are currently rebasing branch 'docs-test' on '5ae56e6'.
  (fix conflicts and then run "git rebase --continue")
  (use "git rebase --skip" to skip this patch)
  (use "git rebase --abort" to check out the original branch)

Unmerged paths:
  (use "git reset HEAD <file>..." to unstage)
  (use "git add <file>..." to mark resolution)

  both modified:   README.md

no changes added to commit (use "git add" and/or "git commit -a")
```

To fix, open all the files with conflicts in your editor and decide which edits
should be applied. Git uses standard conflict-resolution (`<<<<<<<`, `=======`,
and `>>>>>>>`) markers to indicate where in files there are conflicts.

Tip: You can see recent changes made to a file by running the following
commands:
```
git fetch upstream
git log -p upstream/master -- /path/to/file
```
You can use this to compare the changes that you have made to a file with the
ones in upstream, helping you avoid undoing changes from a previous commit when
you are rebasing.

Once you've done that, save the file(s), stage them with `git add` and then
continue the rebase with `git rebase --continue`:

```
$ git add README.md

$ git rebase --continue
Applying: test change for docs
```

For help resolving merge conflicts, see [basic merge
conflicts][gitbook-basic-merge-conflicts], [advanced
merging][gitbook-advanced-merging], and/or GitHub's help on [how to resolve a
merge conflict][github-help-resolve-merge-conflict].

## Working from multiple computers

Working from multiple computers with Zulip and Git is fine, but you'll need to
pay attention and do a bit of work to ensure all of your work is readily
available.

Recall that most Git operations are local. When you commit your changes with
`git commit` they are safely stored in your *local* Git database only. That is,
until you *push* the commits to GitHub, they are only available on the computer
where you committed them.

So, before you stop working for the day, or before you switch computers, push
all of your commits to GitHub with `git push`:

```
$ git push origin <branchname>
```

When you first start working on a new computer, you'll [clone the Zulip
repository][clone-to-your-machine] and [connect it to Zulip
upstream][connect-upstream]. A clone retrieves all current commits,
including the ones you pushed to GitHub from your other computer.

But if you're switching to another computer on which you have already cloned
Zulip, you need to update your local Git database with new refs from your
GitHub fork. You do this with `git fetch`:

```
$ git fetch <usermame>
```

Ideally you should do this before you have made any commits on the same branch
on the second computer. Then you can `git merge` on whichever branch you need
to update:

```
$ git checkout <my-branch>
Switched to branch '<my-branch>'

$ git merge origin/master
```

**If you have already made commits on the second computer that you need to
keep,** you'll need to use `git log FETCH_HEAD` to identify that hashes of the
commits you want to keep and then `git cherry-pick <commit>` those commits into
whichever branch you need to update.

[clone-to-your-machine]: ../git/cloning.html#step-1b-clone-to-your-machine
[connect-upstream]: ../git/cloning.html#step-1c-connect-your-fork-to-zulip-upstream
[gitbook-advanced-merging]: https://git-scm.com/book/en/v2/Git-Tools-Advanced-Merging#_advanced_merging
[gitbook-basic-merge-conflicts]: https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging#Basic-Merge-Conflicts
[gitbook-git-cherry-pick]: https://git-scm.com/docs/git-cherry-pick
[gitbook-reset]: https://git-scm.com/docs/git-reset
[github-help-resolve-merge-conflict]: https://help.github.com/articles/resolving-a-merge-conflict-using-the-command-line/
