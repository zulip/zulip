See also
[fixing commits](https://github.com/zulip/zulip-gci/blob/master/docs/fixing-commits.md)

Commands:

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
    

