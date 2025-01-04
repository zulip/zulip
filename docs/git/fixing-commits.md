# Fixing commits

This is mostly from
[here](https://help.github.com/en/articles/changing-a-commit-message#rewriting-the-most-recent-commit-message).

## Fixing the last commit

### Changing the last commit message

1. `git commit --amend -m "New message"`

### Changing the last commit

1. Make your changes to the files
2. Run `git add <filename>` to add one file or `git add <filename1> <filename2> ...` to add multiple files
3. `git commit --amend`

## Fixing older commits

### Changing commit messages

1. `git rebase -i HEAD~5` (if, for example, you are editing some of the last five commits)
2. For each commit that you want to change the message, change `pick` to `reword`, and save
3. Change the commit messages

### Deleting old commits

1. `git rebase -i HEAD~n` where `n` is the number of commits you are looking at
2. For each commit that you want to delete, change `pick` to `drop`, and save

## Squashing commits

Sometimes, you want to make one commit out of a bunch of commits. To do this,

1. `git rebase -i HEAD~n` where `n` is the number of commits you are interested in
2. Change `pick` to `squash` on the lines containing the commits you want to squash and save

## Reordering commits

1. `git rebase -i HEAD~n` where `n` is the number of commits you are interested in
2. Reorder the lines containing the commits and save

## Changing code in an older commit

If your pull request has multiple commits, a reviewer may request changes that require
you to make changes to an older commit than the latest one. This tends to be more tedious
than just amending the last commit and there can be various approaches, but the most efficient
is by using `git commit --fixup`:

1. Make your changes to the files and stage them, as usual.
1. Identify the hash of the commit you want to modify - for example by copying it from
   `git log --oneline`.
1. Commit your changes as a fixup, by using `git commit --fixup <hash of the commit>`.
1. A new commit with its message starting with `fixup!` has been created. Now you can
   run `git rebase -i --autosquash HEAD~n`, replacing `n` with the number of commits
   to include in the rebase, as in the other sections. In the interactive
   view the commits will be automatically ordered appropriately so that the fixups get
   squashed into the corresponding commits.
1. (Optional) If you want to avoid having to include `--autosquash` every time, you
   can add the following configuration to your `~/.gitconfig`:

   ```
   [rebase]
     autosquash = true
   ```

## Pushing commits after tidying them

1. `git push origin +my-feature-branch` (Note the `+` there and substitute your actual branch name.)
