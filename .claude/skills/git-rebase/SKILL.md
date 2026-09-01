---
name: git-rebase
description: "Squash fixups into earlier commits, reorder commits, or reword commit messages, without needing an interactive editor."
---

# Git Rebase (Non-Interactive)

Since `git rebase -i` requires an interactive editor, use
`GIT_SEQUENCE_EDITOR` to supply the todo list via a script:

1. **Updating the HEAD commit:** If the commit you need to modify is
   already at HEAD, just use `git commit --amend` directly. The
   fixup+rebase workflow below is only needed for non-HEAD commits.

2. **Squashing fixups into existing commits:** Create fixup commits with
   `git commit --fixup=<target-hash>`, then write a shell script that
   outputs the desired todo (with `pick` and `fixup` lines in order)
   and run:

   ```bash
   GIT_SEQUENCE_EDITOR=/path/to/todo-script.sh git rebase -i <base>
   ```

   Note: `--autosquash` alone without `-i` does **not** reorder or
   squash anything.

3. **Rewording commit messages:** Use `git format-patch` to export
   commits as patch files, edit the message headers in the patch
   files, then reapply:

   ```bash
   git format-patch <base> -o /tmp/patches/
   # Edit the commit message in each /tmp/patches/000N-*.patch file
   # (the message is between the Subject: line and the --- line)
   git reset --hard <base>
   git am /tmp/patches/*.patch
   ```
