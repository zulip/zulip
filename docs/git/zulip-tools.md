# Zulip-specific tools

This article documents several useful tools that can save you a lot of
time when working with Git on the Zulip project.

## Set up git repo script

In the `tools` directory of [zulip/zulip][github-zulip-zulip] you'll
find a bash script `setup-git-repo`. This script installs the Zulip
pre-commit hook.  This hook will run each time you `git commit` to
automatically run Zulip's linters on just the files that the commit
modifies. The hook passes no matter the result of the linter, but you
should still pay attention to any notices or warnings it displays.

It's simple to use. Make sure you're in the clone of zulip and run the following:

```
$ ./tools/setup-git-repo
```

The script doesn't produce any output if successful. To check that the hook has
been installed, print a directory listing for `.git/hooks` and you should see
something similar to:

```
$ ls -l .git/hooks
pre-commit -> ../../tools/pre-commit
```

## Set up Travis CI integration

You might also wish to [configure your fork for use with Travis CI][zulip-git-guide-travisci].

## Reset to pull request

`tools/reset-to-pull-request` is a short-cut for [checking out a pull request
locally][zulip-git-guide-fetch-pr]. It works slightly differently from the method
described above in that it does not create a branch for the pull request
checkout.

**This tool checks for uncommitted changes, but it will move the
  current branch using `git reset --hard`.  Use with caution.**

First, make sure you are working in a branch you want to move (in this
example, we'll use the local `master` branch). Then run the script
with the ID number of the pull request as the first argument.

```
$ git checkout master
Switched to branch 'master'
Your branch is up-to-date with 'origin/master'.

$ ./tools/reset-to-pull-request 1900
+ request_id=1900
+ git fetch upstream pull/1900/head
remote: Counting objects: 159, done.
remote: Compressing objects: 100% (17/17), done.
remote: Total 159 (delta 94), reused 91 (delta 91), pack-reused 51
Receiving objects: 100% (159/159), 55.57 KiB | 0 bytes/s, done.
Resolving deltas: 100% (113/113), completed with 54 local objects.
From https://github.com/zulip/zulip
 * branch            refs/pull/1900/head -> FETCH_HEAD
+ git reset --hard FETCH_HEAD
HEAD is now at 2bcd1d8 troubleshooting tip about provisioning
```

## Fetch a pull request and rebase

`tools/fetch-rebase-pull-request` is a short-cut for [checking out a pull
request locally][zulip-git-guide-fetch-pr] in its own branch and then updating it with any
changes from upstream/master with `git rebase`.

Run the script with the ID number of the pull request as the first argument.

```
$ tools/fetch-rebase-pull-request 1913
+ request_id=1913
+ git fetch upstream pull/1913/head
remote: Counting objects: 4, done.
remote: Compressing objects: 100% (4/4), done.
remote: Total 4 (delta 0), reused 0 (delta 0), pack-reused 0
Unpacking objects: 100% (4/4), done.
From https://github.com/zulip/zulip
 * branch            refs/pull/1913/head -> FETCH_HEAD
+ git checkout upstream/master -b review-1913
Branch review-1913 set up to track remote branch master from upstream.
Switched to a new branch 'review-1913'
+ git reset --hard FETCH_HEAD
HEAD is now at 99aa2bf Add provision.py fails issue in common erros
+ git pull --rebase
Current branch review-1913 is up to date.
```

## Fetch a pull request without rebasing

`tools/fetch-pull-request` is a similar to `tools/fetch-rebase-pull-request`, but
it does not rebase the pull request against upstream/master, thereby getting
exactly the same repository state as the commit author had.

Run the script with the ID number of the pull request as the first argument.

```
$ tools/fetch-pull-request 5156
+ git diff-index --quiet HEAD
+ request_id=5156
+ remote=upstream
+ git fetch upstream pull/5156/head
From https://github.com/zulip/zulip
 * branch            refs/pull/5156/head -> FETCH_HEAD
+ git checkout -B review-original-5156
Switched to a new branch 'review-original-5156'
+ git reset --hard FETCH_HEAD
HEAD is now at 5a1e982 tools: Update clean-branches to clean review branches.
```

## Delete unimportant branches

`tools/clean-branches` is a shell script that removes branches that are either:

1. Local branches that are ancestors of origin/master.
2. Branches in origin that are ancestors of origin/master and named like `$USER-*`.
3. Review branches created by `tools/fetch-rebase-pull-request` and `tools/fetch-pull-request`.

First, make sure you are working in branch `master`. Then run the script without any
arguments for default behavior. Since removing review branches can inadvertently remove any
feature branches whose names are like `review-*`, it is not done by default. To
use it, run `tools/clean-branches --reviews`.

```
$ tools/clean-branches --reviews
Deleting local branch review-original-5156 (was 5a1e982)
```

## Merge conflict on yarn.lock file

If there is a merge conflict on yarn.lock, yarn should be run to
regenerate the file. *Important* don't delete the yarn.lock file. Checkout the
latest one from origin/master so that yarn knows the previous asset versions.

Run the following commands
```
git checkout origin/master -- yarn.lock
yarn install
git add yarn.lock
git rebase --continue
```

[github-zulip-zulip]: https://github.com/zulip/zulip/
[zulip-git-guide-fetch-pr]: ../git/collaborate.html#checkout-a-pull-request-locally
[zulip-git-guide-travisci]: ../git/cloning.html#step-3-configure-travis-ci-continuous-integration
