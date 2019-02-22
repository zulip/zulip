# How Git is different

Whether you're new to Git or have experience with another version control
system (VCS), it's a good idea to learn a bit about how Git works. We recommend
this excellent presentation *[Understanding Git][understanding-git]* from
Nelson Elhage and Anders Kaseorg and the [Git Basics][gitbook-basics] chapter
from *Pro Git* by Scott Chacon and Ben Straub.

Here are the top things to know:

- **Git works on snapshots:** Unlike other version control systems (e.g.,
  Subversion, Perforce, Bazaar), which track files and changes to those files
  made over time, Git tracks *snapshots* of your project. Each time you commit
  or otherwise make a change to your repository, Git takes a snapshot of your
  project and stores a reference to that snapshot. If a file hasn't changed,
  Git creates a link to the identical file rather than storing it again.

- **Most Git operations are local:** Git is a distributed version control
  system, so once you've cloned a repository, you have a complete copy of that
  repository's *entire history*. Staging, committing, branching, and browsing
  history are all things you can do locally without network access and without
  immediately affecting any remote repositories. To make or receive changes
  from remote repositories, you need to `git fetch`, `git pull`, or `git push`.

- **Nearly all Git actions add information to the Git database**, rather than
  removing it. As such, it's hard to make Git perform actions that you can't
  undo. However, Git can't undo what it doesn't know about, so it's a good
  practice to frequently commit your changes and frequently push your commits to
  your remote repository.

- **Git is designed for lightweight branching and merging.** Branches are
  simply references to snapshots. It's okay and expected to make a lot of
  branches, even throwaway and experimental ones.

- **Git stores all data as objects, of which there are four types:** blob
  (file), tree (directory), commit (revision), and tag. Each of these objects
  is named by a unique hash, the SHA-1 hash of its contents. Most of the time
  you'll refer to objects by their truncated hash or more human-readable
  reference like `HEAD` (the current branch). Blobs and trees represent files
  and directories. Tags are named references to other objects. A commit object
  includes: tree id, zero or more parents as commit ids, an author (name,
  email, date), a committer (name, email, date), and a log message. A Git
  repository is a collection of mutable pointers to these objects called
  **refs**.

- **Cloning a repository creates a working copy.** Every working copy has a
  `.git` subdirectory, which contains its own Git repository. The `.git`
  subdirectory also tracks the *index*, a staging area for changes that will
  become part of the next commit. All files outside of `.git` is the *working
  tree*.

- **Files tracked with Git have possible three states: committed, modified, and
  staged.** Committed files are those safely stored in your local `.git`
  repository/database. Staged files have changes and have been marked for
  inclusion in the next commit; they are part of the index. Modified files have
  changes but have not yet been marked for inclusion in the next commit; they
  have not been added to the index.

- **Git commit workflow is as follows:** Edit files in your *working tree*. Add
  to the *index* (that is *stage*) with `git add`. *Commit* to the HEAD of the
  current branch with `git commit`.

[gitbook-basics]: https://git-scm.com/book/en/v2/Getting-Started-Git-Basics
[understanding-git]: http://web.mit.edu/nelhage/Public/git-slides-2009.pdf
