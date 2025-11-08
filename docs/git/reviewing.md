# Review changes

**Note** - The following section covers reviewing changes on your local
clone. Please read the section on [code reviews][zulip-rtd-review] for a guide
on reviewing changes by other contributors.

## Changes on (local) working tree

Display changes between index and working tree (what is not yet staged for commit):

```console
$ git diff
```

Display changes between index and last commit (what you have staged for commit):

```console
$ git diff --cached
```

Display changes in working tree since last commit (changes that are staged as
well as ones that are not):

```console
$ git diff HEAD
```

## Changes within branches

Use any git-ref to compare changes between two commits on the current branch.

Display changes between commit before last and last commit:

```console
$ git diff HEAD^ HEAD
```

Display changes between two commits using their hashes:

```console
$ git diff e2f404c 7977169
```

## Changes between branches

Display changes between tip of `topic` branch and tip of `main` branch:

```console
$ git diff topic main
```

Display changes that have occurred on `main` branch since `topic` branch was created:

```console
$ git diff topic...main
```

Display changes you've committed so far since creating a branch from `upstream/main`:

```console
$ git diff upstream/main...HEAD
```

[zulip-rtd-review]: ../contributing/code-reviewing.md
