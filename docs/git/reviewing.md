# Review changes

**Note** - The following section covers reviewing changes on your local
clone. Please read the section on [code reviews][zulip-rtd-review] for a guide
on reviewing changes by other contributors.

## Changes on (local) working tree

Display changes between index and working tree (what is not yet staged for commit):

```
$ git diff
```

Display changes between index and last commit (what you have staged for commit):

```
$ git diff --cached
```

Display changes in working tree since last commit (changes that are staged as
well as ones that are not):

```
$ git diff HEAD
```

## Changes within branches

Use any git-ref to compare changes between two commits on the current branch.

Display changes between commit before last and last commit:

```
$ git diff HEAD^ HEAD
```

Display changes between two commits using their hashes:

```
$ git diff e2f404c 7977169
```

## Changes between branches

Display changes between tip of topic branch and tip of master branch:

```
$ git diff topic master
```

Display changes that have occurred on master branch since topic branch was created:

```
$ git diff topic...master
```

Display changes you've committed so far since creating a branch from upstream/master:

```
$ git diff upstream/master...HEAD
```

[zulip-rtd-review]: ../contributing/code-reviewing.html
