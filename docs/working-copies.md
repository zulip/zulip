## Intro

When you work on Zulip code, there are three working copies
of the Zulip git repo that you are generally concerned with:

- local copy: This lives on your laptop or your remove dev instance.
- forked copy: This lives on GitHub, and it's tied to your account.
- official Zulip repo: https://github.com/zulip/zulip

We sometimes call the forked copy the **origin** remote.

We sometimes call the official repo the **upstream** remote.

When you work on Zulip code, you will end up moving code between
the various working copies.

## Workflows

Sometimes you need to get commits.  Here are some scenarios:

- You may fork the official Zulip repo to your Github fork.
- You may fetch commits from the offical Zulip repo to your local copy.
- You occasionally may fetch commits from your forked copy.

Sometimes you want to publish commits.  Here are scenarios:

- You push code from your local copy to your Github fork.  (You usually
  want to put the commit on a feature branch.)
- You submit a PR to the official Zulip repo.

Finally, the Zulip core team will occasionally want your changes!

- The Zulip core team can accept your changes and add them to
  the official repo, usually on the master branch.
  
## Names

We call remote working copies of the repository by these short
names.

- **origin**: This is your fork.
- **upstream**: This is the official Zulip repo.

## Relevant git commands

The following commands are useful for moving commits between
working copies:

- `git fetch`: This grabs code from another repo to your local copy.
- `git push`: This pushes code from your local repo to one of the remotes.
- `git remote`: This helps you configure short names for remotes.  (Your
  mentor can help you with this.)
- `git pull`: **Do not use this, please**!

