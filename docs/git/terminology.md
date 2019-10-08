# Important Git terms

When you install Git, it adds a manual entry for `gitglossary`. You can view
this glossary by running `man gitglossary`. Below we've included the git terms
you'll encounter most often along with their definitions from *gitglossary*.

## branch
A "branch" is an active line of development. The most recent commit
on a branch is referred to as the tip of that branch. The tip of
the branch is referenced by a branch head, which moves forward as
additional development is done on the branch. A single Git
repository can track an arbitrary number of branches, but your
working tree is associated with just one of them (the "current" or
"checked out" branch), and HEAD points to that branch.

## cache
Obsolete for: index

## checkout
The action of updating all or part of the working tree with a tree
object or blob from the object database, and updating the index and
HEAD if the whole working tree has been pointed at a new branch.

## commit
As a noun: A single point in the Git history; the entire history of
a project is represented as a set of interrelated commits. The word
"commit" is often used by Git in the same places other revision
control systems use the words "revision" or "version". Also used as
a short hand for commit object.

As a verb: The action of storing a new snapshot of the project's
state in the Git history, by creating a new commit representing the
current state of the index and advancing HEAD to point at the new

## fast-forward
A fast-forward is a special type of merge where you have a revision
and you are "merging" another branch's changes that happen to be a
descendant of what you have. In such these cases, you do not make a
new mergecommit but instead just update to their revision. This will
happen frequently on a remote-tracking branch of a remote
repository.

## fetch
Fetching a branch means to get the branch's head ref from a remote
repository, to find out which objects are missing from the local
object database, and to get them, too. See also git-fetch(1).

## hash
In Git's context, synonym for object name.

## head
A named reference to the commit at the tip of a branch. Heads are
stored in a file in $GIT_DIR/refs/heads/ directory, except when
using packed refs. (See git-pack-refs(1).)

## HEAD
The current branch. In more detail: Your working tree is normally
derived from the state of the tree referred to by HEAD. HEAD is a
reference to one of the heads in your repository, except when using
a detached HEAD, in which case it directly references an arbitrary
commit.

## index
A collection of files with stat information, whose contents are
stored as objects. The index is a stored version of your working
tree. Truth be told, it can also contain a second, and even a third
version of a working tree, which are used when merging.

## pull
Pulling a branch means to fetch it and merge it. See also git-
pull(1).

## push
Pushing a branch means to get the branch's head ref from a remote
repository, find out if it is a direct ancestor to the branch's
local head ref, and in that case, putting all objects, which are
reachable from the local head ref, and which are missing from the
remote repository, into the remote object database, and updating
the remote head ref. If the remote head is not an ancestor to the
local head, the push fails.

## rebase
To reapply a series of changes from a branch to a different base,
and reset the head of that branch to the result.
