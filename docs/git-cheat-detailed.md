See also
[fixing commits](https://github.com/zulip/zulip-gci/blob/master/docs/fixing-commits.md)

Commands:

- add
    - `git add foo.py`: add `foo.py` to the staging area
    - `git add foo.py bar.py`: add `foo.py` AND `bar.py` to the staging area
- checkout
    - `git checkout -b new-branch-name`: create branch `new-branch-name` and switch/checkout to that new branch
    - `git checkout master`: switch to your `master` branch
    - `git checkout old-branch-name`: switch to an existing branch `old-branch-name`
- commit
    - `git commit --amend`: changing the last commit message. Read more [here](https://github.com/zulip/zulip-gci/blob/master/docs/fixing-commits.md)
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
    - **do not use for Zulip**
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
    

