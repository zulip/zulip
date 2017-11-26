# Git Cheat Sheet

See also [fixing commits][fix-commit]

## Common Commands

- add
    - `git add foo.py`
- checkout
    - `git checkout -b new-branch-name`
    - `git checkout master`
    - `git checkout old-branch-name`
- commit
    - `git commit --amend`
- config
    - `git config --global core.editor nano`
    - `git config --global core.symlinks true`
- diff
    - `git diff`
    - `git diff --cached`
    - `git diff HEAD~2..`
- fetch
    - `git fetch origin`
    - `git fetch upstream`
- grep
    - `git grep update_unread_counts -- '*.js'`
- log
    - `git log`
- pull
    - **do not use for Zulip**
- push
    - `git push origin +branch-name`
- rebase
    - `git rebase -i HEAD~3`
    - `git rebase -i master`
    - `git rebase upstream/master`
- reflog
    - `git reflog | head -10`
- remote
    - `git remote -v`
- reset
    - `git reset HEAD~2`
- rm
    - `git rm oops.txt`
- show
    - `git show HEAD`
    - `git show HEAD~~~`
    - `git show master`
- status
    - `git status`

## Detailed Cheat Sheet

- add
    - `git add foo.py`: add `foo.py` to the staging area
    - `git add foo.py bar.py`: add `foo.py` AND `bar.py` to the staging area
- checkout
    - `git checkout -b new-branch-name`: create branch `new-branch-name` and switch/checkout to that new branch
    - `git checkout master`: switch to your `master` branch
    - `git checkout old-branch-name`: switch to an existing branch `old-branch-name`
- commit
    - `git commit --amend`: changing the last commit message. Read more [here][fix-commit]
- config
    - `git config --global core.editor nano`: set core editor to `nano` (you can set this to `vim` or others)
    - `git config --global core.symlinks true`: allow symbolic links
- diff
    - `git diff`: display the changes you have made to all files
    - `git diff --cached`: display the changes you have made to staged files
    - `git diff HEAD~2..`: display the 2 most recent changes you have made to files
- fetch
    - `git fetch origin`: fetch origin repository
    - `git fetch upstream`: fetch upstream repository
- grep
    - `git grep update_unread_counts -- '*.js'`: search all files (ending in `.js`) for `update_unread_counts`
- log
    - `git log`: show commit logs
- pull
    - `git pull --rebase`: rebase your changes on top of master.
    - `git pull` (with no options): Will either create a merge commit
      (which you don't want) or do the asme as `git pull --rebase`,
      depending on [whether you're configured Git properly][git-clone-config]
- push
    - `git push origin +branch-name`: push your commits to your origin repository
- rebase
    - `git rebase -i HEAD~3`: interactive rebasing current branch with first three items on HEAD
    - `git rebase -i master`: interactive rebasing current branch with master branch
    - `git rebase upstream/master`: rebasing current branch with master branch from upstream repository
- reflog
    - `git reflog | head -10`: manage reference logs for the past 10 commits
- remote
    - `git remote -v`: display your origin and upstream repositories
- reset
    - `git reset HEAD~2`: reset two most recent commits
- rm
    - `git rm oops.txt`: remove `oops.txt`
- show
    - `git show HEAD`: display most recent commit
    - `git show HEAD~~~`: display third most recent commit
    - `git show master`: display most recent commit on `master`
- status
    - `git status`: show the working tree status, unstaged and staged files

[fix-commit]: fixing-commits.html
[git-config-clone]: cloning.html#step-1b-clone-to-your-machine
