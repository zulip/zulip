# Collaborate

## Fetch another contributor's branch

What happens when you would like to collaborate with another contributor and
they have work-in-progress on their own fork of Zulip? No problem! Just add
their fork as a remote and pull their changes.

```
$ git remote add <username> https://github.com/<username>/zulip.git
$ git fetch <username>
```

Now you can checkout their branch just like you would any other. You can name
the branch anything you want, but using both the username and branch name will
help you keep things organized.

```
$ git checkout -b <username>/<branchname>
```

You can choose to rename the branch if you prefer:
```
git checkout -b <custombranchname> <username>/<branchname>
```

## Checkout a pull request locally

Just as you can checkout any user's branch locally, you can also checkout any
pull request locally. GitHub provides a special syntax
([details][github-help-co-pr-locally]) for this since pull requests are
specific to GitHub rather than Git.

First, fetch and create a branch for the pull request, replacing *ID* and
*BRANCHNAME* with the ID of the pull request and your desired branch name:

```
$ git fetch upstream pull/ID/head:BRANCHNAME
```

Now switch to the branch:

```
$ git checkout BRANCHNAME
```

Now you work on this branch as you would any other.

Note: you can use the scripts provided in the tools/ directory to fetch pull
requests. You can read more about what they do [here][tools-PR].
```
tools/fetch-rebase-pull-request <PR-number>
tools/fetch-pull-request <PR-number>
```

[github-help-co-pr-locally]: https://help.github.com/en/articles/checking-out-pull-requests-locally
[tools-PR]: ../git/zulip-tools.html#fetch-a-pull-request-and-rebase
