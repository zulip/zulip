# Create a pull request

When you're ready for feedback, submit a pull request. Pull requests
are a feature specific to GitHub. They provide a simple, web-based way
to submit your work (often called "patches") to a project. It's called
a *pull request* because you're asking the project to *pull changes*
from your fork.

If you're unfamiliar with how to create a pull request, you can check
out GitHub's documentation on
[creating a pull request from a fork][github-help-create-pr-fork]. You
might also find GitHub's article
[about pull requests][github-help-about-pr] helpful. That all said,
the tutorial below will walk you through the process.

## Work in progress pull requests

In the Zulip project, we encourage submitting work-in-progress pull
requests early and often. This allows you to share your code to make
it easier to get feedback and help with your changes. Prefix the
titles of work-in-progress pull requests with **[WIP]**, which in our
project means that you don't think your pull request is ready to be
merged (e.g. it might not work or pass tests).  This sets expectations
correctly for any feedback from other developers, and prevents your
work from being merged before you're confident in it.

## Create a pull request

### Step 1: Update your branch with git rebase

The best way to update your branch is with `git fetch` and `git rebase`. Do not
use `git pull` or `git merge` as this will create merge commits. See [keep your
fork up to date][keep-up-to-date] for details.

Here's an example (you would replace *issue-123* with the name of your feature branch):

```
$ git checkout issue-123
Switched to branch 'issue-123'

$ git fetch upstream
remote: Counting objects: 69, done.
remote: Compressing objects: 100% (23/23), done.
remote: Total 69 (delta 49), reused 39 (delta 39), pack-reused 7
Unpacking objects: 100% (69/69), done.
From https://github.com/zulip/zulip
   69fa600..43e21f6  master     -> upstream/master

$ git rebase upstream/master

First, rewinding head to replay your work on top of it...
Applying: troubleshooting tip about provisioning
```

### Step 2: Push your updated branch to your remote fork

Once you've updated your local feature branch, push the changes to GitHub:

```
$ git push origin issue-123
Counting objects: 6, done.
Delta compression using up to 4 threads.
Compressing objects: 100% (4/4), done.
Writing objects: 100% (6/6), 658 bytes | 0 bytes/s, done.
Total 6 (delta 3), reused 0 (delta 0)
remote: Resolving deltas: 100% (3/3), completed with 1 local objects.
To git@github.com:christi3k/zulip.git
 + 2d49e2d...bfb2433 issue-123 -> issue-123
```

If your push is rejected with error **failed to push some refs** then you need
to prefix the name of your branch with a `+`:

```
$ git push origin +issue-123
Counting objects: 6, done.
Delta compression using up to 4 threads.
Compressing objects: 100% (4/4), done.
Writing objects: 100% (6/6), 658 bytes | 0 bytes/s, done.
Total 6 (delta 3), reused 0 (delta 0)
remote: Resolving deltas: 100% (3/3), completed with 1 local objects.
To git@github.com:christi3k/zulip.git
 + 2d49e2d...bfb2433 issue-123 -> issue-123 (forced update)
```

This is perfectly okay to do on your own feature branches, especially if you're
the only one making changes to the branch. If others are working along with
you, they might run into complications when they retrieve your changes because
anyone who has based their changes off a branch you rebase will have to do a
complicated rebase.

### Step 3: Open the pull request

If you've never created a pull request or need a refresher, take a look at
GitHub's article [creating a pull request from a
fork][github-help-create-pr-fork]. We'll briefly review the process here.

The first step in creating a pull request is to use your web browser to
navigate to your fork of Zulip. Sign in to GitHub if you haven't already.

Next, navigate to the branch you've been working on. Do this by clicking on the
**Branch** button and selecting the relevant branch. Finally, click the **New
pull request** button.

Alternatively, if you've recently pushed to your fork, you will see a green
**Compare & pull request** button.

You'll see the *Open a pull request* page:

![images-create-pr]

Provide a **title** and first comment for your pull request. Remember to prefix
your pull request title with [WIP] if it is a [work-in-progress][wip-prs].

If your pull request has an effect on the visuals of a component, you might want
to include a screenshot of this change or a GIF of the interaction in your first
comment. This will allow reviewers to comment on your changes without having to
checkout your branch; you can find a list of tools you can use for this over
[here][screenshots-gifs].

When ready, click the green **Create pull request** to submit the pull request.

Note: **Pull request titles are different from commit messages.** Commit
messages can be edited with `git commit --amend`, `git rebase -i`, etc., while
the title of a pull request can only be edited via GitHub.

## Update a pull request

As you get make progress on your feature or bugfix, your pull request, once
submitted, will be updated each time you [push commits][self-push-commits] to
your remote branch. This means you can keep your pull request open as long as
you need, rather than closing and opening new ones for the same feature or
bugfix.

It's a good idea to keep your pull request mergeable with Zulip upstream by
frequently fetching, rebasing, and pushing changes. See [keep your fork up to
date][keep-up-to-date] for details. You might also find this excellent
article [How to Rebase a Pull Request][edx-howto-rebase-pr] helpful.

And, as you address review comments others have made, we recommend posting a
follow-up comment in which you: a) ask for any clarifications you need, b)
explain to the reviewer how you solved any problems they mentioned, and c) ask
for another review.

[edx-howto-rebase-pr]: https://github.com/edx/edx-platform/wiki/How-to-Rebase-a-Pull-Request
[github-help-about-pr]: https://help.github.com/en/articles/about-pull-requests
[github-help-create-pr-fork]: https://help.github.com/en/articles/creating-a-pull-request-from-a-fork
[images-create-pr]: ../images/zulip-open-pr.png
[keep-up-to-date]: ../git/using.html#keep-your-fork-up-to-date
[push-commits]: ../git/using.html#push-your-commits-to-github
[screenshots-gifs]: ../tutorials/screenshot-and-gif-software.html
[wip-prs]: #work-in-progress-pull-requests
