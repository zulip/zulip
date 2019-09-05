# Modifying or patching Zulip

Zulip is 100% free and open source software, and you're welcome to
modify it!  This page explains how to make and maintain modifications
in a safe and convenient fashion.

If you do modify Zulip and then report an issue you see in your
modified version of Zulip, please be responsible about communicating
that fact:

* Ideally, you'd reproduce the issue in an unmodified version (e.g. on
[chat.zulip.org](../contributing/chat-zulip-org.html) or
[zulipchat.com](https://zulipchat.com)).
* Where that is difficult or you think it's very unlikely your changes
are related to the issue, just mention your changes in the issue report.

## Making changes

One way to modify Zulip is to just edit files under
`/home/zulip/deployments/current` and then restart the server.  This
can work OK for testing small changes to Python code or shell scripts.
But we don't recommend this approach for maintaining changes because:

* You cannot modify JavaScript, CSS, or other frontend files this way,
  because we don't include them in editable form in our production
  release tarballs (doing so would make our release tarballs much
  larger without any runtime benefit).
* You will need to redo your changes after you next upgrade your Zulip
  server (or they will be lost).
* You need to remember to restart the server or your changes won't
  have effect.
* Your changes aren't tracked, so mistakes can be hard to debug.

Instead, we recommend the following GitHub-based workflow (see [our
Git guide][git-guide] if you need a primer):

* Decide where you're going to edit Zulip's code.  We recommend [using
  the Zulip development environment](../development/overview.html) on
  a desktop or laptop as it will make it extremely convenient for you
  to test your changes without deploying them in production.  But if
  your changes are small or you're OK with risking downtime, you don't
  strictly need it; you just need an environment with Git installed.
* **Important**.  Determine what Zulip version you're running on your
  server.  You can check by inspecting `ZULIP_VERSION` in
  `/home/zulip/deployments/current/version.py` (we'll use `2.0.4`
  below).  If you apply your changes to the wrong version of Zulip,
  it's likely to fail and potentially cause downtime.
* [Fork and clone][fork-clone] the [zulip/zulip][] repository on
  [GitHub](https://github.com).
* Create a branch (named `acme-branch` below) containing your changes:

```
cd zulip
git checkout -b acme-branch 2.0.4
```

* Use your favorite code editor to modify Zulip.
* Commit your changes and push them to GitHub:

```
git commit -a

# Use `git diff` to verify your changes are what you expect
git diff 2.0.4 acme-branch

# Push the changes to your GitHub fork
git push origin +acme-branch
```

* Login to your Zulip server and configure and use
[upgrade-zulip-from-git][] to install the changes; remember to
configure `git_repo_url` to point to your fork on GitHub and run it as
`upgrade-zulip-from-git acme-branch`.

This workflow solves all of the problems described above: your change
will be compiled and installed correctly (restarting the server), and
your changes will be tracked so that it's convenient to maintain them
across future Zulip releases.

### Upgrading to future releases

Eventually, you'll want to upgrade to a new Zulip release
(e.g. `2.1.0` in this example).  If your changes were integrated into
that Zulip release or are otherwise no longer needed, you can just use
[upgrade-zulip][upgrade-zulip] as usual.  Otherwise, you'll need to
update your branch by rebasing your changes (starting from a
[clone][fork-clone] of the [zulip/zulip][] repository):

```
cd zulip
git fetch --tags upstream
git checkout acme-branch
git rebase 2.1.0
# Fix any errors or merge conflicts; see Zulip's Git Guide for advice

# Use `git diff` to verify your changes are what you expect
git diff 2.1.0 acme-branch

git push origin +acme-branch
```

And then use [upgrade-zulip-from-git][] to install your updated
branch, as before.

### Making changes with docker-zulip

If you are using [docker-zulip][], there are two things that are
different from the above:

* Because of how container images work, editing files directly is even
  more precarious, because Docker is designed for working with
  container images and may lose your changes.
* Instead of running `upgrade-zulip-from-git`, you will need to use
  the [docker upgrade workflow][docker-zulip-upgrade] to build a
  container image based on your modified version of Zulip.

[docker-zulip]: https://github.com/zulip/docker-zulip
[docker-zulip-upgrade]: https://github.com/zulip/docker-zulip#upgrading-from-a-git-repository

## Applying changes from master

If you are experiencing an issue that has already been fixed by the
Zulip development community, and you'd like to get the fix now, you
have a few options.  There are two possible ways you might get those
fixes on your local Zulip server without waiting for an official release.

### Applying a small change

Many bugs have small/simple fixes.  In this case, you can use the Git
workflow [described above](#making-changes), using:

```
git fetch upstream
git cherry-pick abcd1234
```

instead of "making changes locally" (where `abcd1234` is the commit ID
of the change you'd like).

In general, we can't provide community support for issues caused by
cherry-picking changes in this way.  There is a major exception to
this rule.

Zulip can be deployed in a wide variety of configurations and
environments, and so we often merge fixes to bugs that we can
reproduce in an automated test but have not directly reproduced in a
production system.  In these cases, we'll ask the user(s) who reported
the bug to apply the patch to their production system to verify the
fix works for them.

Generally, we'll only request this if we expect the fix in question to
apply cleanly to the latest release without introducing regressions,
and you can expect the Zulip community to be responsive in debugging
any problems any caused by the patch.

### Upgrading to master

It's unsafe to backport arbitrary patches from master to an older
version.  Common issues include:

* Changes containing database migrations (new files under
  `zerver/migrations/`), which includes most new major features.  We
  don't support applying database migrations out of order.
* Changes that are stacked on top of other changes to the same system.
* Essentially any patch with hundreds of lines of changes.

While it's possible to backport these sorts of changes, you're
unlikely to succeed without help from the core team via a support
contract.

If you need an unreleased feature, the right path is usually to Zulip
master using [upgrade-zulip-from-git][].  Before upgrading to master,
make sure you understand:

* The `master` branch is under very active development; dozens of new
  changes are integrated into it on most days.  Master can have
  thousands of changes not present in the latest release (all of which
  will be included in our next release).  There are probably some
  bugs.
* That said we deploy master to chat.zulip.org and zulipchat.com on a
  regular basis (often daily), so it's very important to the project
  that it be stable.  Most regressions will be minor UX issues or be
  fixed quickly.
* The development community is very interested in helping debug issues
  that arise when upgrading from the latest release to master, since
  they provide us an opportunity to fix that category of issue before
  our next major release.  (Much more so than we are in helping folks
  debug other custom changes).  That said, we cannot make any
  guarantees about how quickly we'll resolve an issue to folks without
  a formal support contract.
* We do not support downgrading from master to earlier versions, so if downtime
  for your Zulip server is unacceptable, make sure you have a current
  backup in case the upgrade fails.

## Contributing patches

Zulip contains thousands of changes submitted by volunteer
contributors like you.  If your changes are likely to be of useful to
other organizations, consider [contributing
them](../overview/contributing.html).

[fork-clone]: ../git/cloning.html#get-zulip-code
[upgrade-zulip-from-git]: ../production/maintain-secure-upgrade.html#upgrading-from-a-git-repository
[upgrade-zulip]: ../production/maintain-secure-upgrade.html#upgrading
[git-guide]: ../git/index.html
[zulip/zulip]: https://github.com/zulip/zulip/
