# Fixing Commits
This is mostly from
[here](https://help.github.com/articles/changing-a-commit-message/#rewriting-the-most-recent-commit-message).

## Fixing the last commit
### Changing the last commit message
1. `git commit --amend -m "New Message"`

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

## Pushing commits after tidying them
1. `git push origin +my-feature-branch`  (Note the `+` there and substitute your actual branch name.)
