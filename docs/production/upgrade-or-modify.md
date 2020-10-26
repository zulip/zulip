# Upgrade or modify Zulip

This page explains how to upgrade, patch, or modify Zulip, including:

- [Upgrading to a release](#upgrading-to-a-release)
- [Upgrading from a Git repository](#upgrading-from-a-git-repository)
- [Troubleshooting and rollback](#troubleshooting-and-rollback)
- [Preserving local changes to configuration files](#preserving-local-changes-to-configuration-files)
- [Upgrading the operating system](#upgrading-the-operating-system)
- [Upgrading PostgreSQL](#upgrading-postgresql)
- [Modifying Zulip](#modifying-zulip)
- [Applying changes from master](#applying-changes-from-master)

## Upgrading to a release

Note that there are additional instructions if you're [using
docker-zulip][docker-upgrade], have [patched Zulip](#modifying-zulip),
or have [modified Zulip-managed configuration
files](#preserving-local-changes-to-configuration-files).  To upgrade
to a new Zulip release:

1. Read the [upgrade notes](../overview/changelog.html#upgrade-notes)
   for all releases newer than what is currently installed.

1. Download the appropriate release tarball from
    <https://www.zulip.org/dist/releases/> You can download the latest
    release with:

    ```
    wget https://www.zulip.org/dist/releases/zulip-server-latest.tar.gz
    ```

    You also have the option of upgrading Zulip [to a version in a Git
    repository directly](#upgrading-from-a-git-repository) or creating
    your own release tarballs from a copy of the [zulip.git
    repository](https://github.com/zulip/zulip) using
    `tools/build-release-tarball`.

1. Log in to your Zulip and run as root:

    ```
    /home/zulip/deployments/current/scripts/upgrade-zulip zulip-server-VERSION.tar.gz
    ```

    The upgrade process will:
    * Run `apt-get upgrade`
    * Install new versions of Zulip's dependencies (mainly Python packages).
    * (`upgrade-zulip-from-git` only) Build Zulip's frontend assets using `webpack`.
    * Shut down the Zulip service
    * Run a `puppet apply`
    * Run any database migrations
    * Bring the Zulip service back up on the new version.

Upgrading will result in brief downtime for the service, which should
be under 30 seconds unless there is an expensive database migration
involved (these will be documented in the [release
notes](../overview/changelog.md), and usually can be avoided with
some care).  If downtime is problematic for your organization,
consider testing the upgrade on a
[backup](../production/export-and-import.html#backups) in advance,
doing the final upgrade at off hours, or buying a support contract.

See the [troubleshooting guide](#troubleshooting-and-rollback) if you
run into any issues or need to roll back the upgrade.

## Upgrading from a Git repository

Zulip supports upgrading a production installation to any commit in a
Git repository, which is great for [running pre-release changes from
master](#applying-changes-from-master) or [maintaining a
fork](#making-changes).  The process is simple:

```
# Upgrade to an official release
/home/zulip/deployments/current/scripts/upgrade-zulip-from-git 1.8.1
# Upgrade to a branch (or other Git ref)
/home/zulip/deployments/current/scripts/upgrade-zulip-from-git 2.1.x
/home/zulip/deployments/current/scripts/upgrade-zulip-from-git master
```

Zulip will automatically fetch the relevant Git commit and upgrade to
that version of Zulip.

Branches with names like `2.1.x` are stable release branches,
containing the changes planned for the next minor release
(E.g. 2.1.5); we support these stable release branches as though they
were a published release.

The `master` branch contains changes planned for the next major
release (E.g. 3.0); see our documentation on [running
master](#upgrading-to-master) before upgrading to it.

By default, this uses the main upstream Zulip server repository, but
you can configure any other Git repository by adding a section like
this to `/etc/zulip/zulip.conf`:

```
[deployment]
git_repo_url = https://github.com/zulip/zulip.git
```

See also our documentation on [upgrading
docker-zulip](https://github.com/zulip/docker-zulip#upgrading-from-a-git-repository).

## Troubleshooting and rollback

See also the general Zulip server [troubleshooting
guide](../production/troubleshooting.md).

The upgrade scripts are idempotent, so there's no harm in trying again
after resolving an issue.  The most common causes of errors are:

* Networking issues (e.g. your Zulip server doesn't have reliable
  Internet access or needs a proxy set up).  Fix the networking issue
  and try again.
* Especially when using `upgrade-zulip-from-git`, systems with the
  minimal RAM for running Zulip can run into out-of-memory issues
  during the upgrade process (generally `tools/webpack` is the step
  that fails).  You can get past this by shutting down the Zulip
  server with `supervisorctl stop all` to free up RAM before running
  the upgrade process.

Useful logs are available in a few places:
* The Zulip upgrade scripts log all output to
  `/var/log/zulip/upgrade.log`.
* The Zulip server logs all Internal Server Errors to
  `/var/log/zulip/errors.log`.

If you need help and don't have a support contract, you can visit
[#production
help](https://chat.zulip.org/#narrow/stream/31-production-help) in the
[Zulip development community
server](../contributing/chat-zulip-org.md) for best-effort help.
Please include the relevant error output from the above logs in a
[Markdown code
block](https://zulip.com/help/format-your-message-using-markdown#code)
in any reports.

### Rolling back to a prior version

This rollback process is intended for minor releases (e.g. `2.0.3` to
`2.0.6`); a more complicated process is required to roll back database
migrations before downgrading to an older major release.

The Zulip upgrade process works by creating a new deployment under
`/home/zulip/deployments/` containing a complete copy of the Zulip server code,
and then moving the symlinks at `/home/zulip/deployments/{current,last,next}`
as part of the upgrade process.

This means that if the new version isn't working,
you can quickly downgrade to the old version by running
`/home/zulip/deployments/last/scripts/restart-server`, or to an
earlier previous version by running
`/home/zulip/deployments/DATE/scripts/restart-server`.  The
`restart-server` script stops any running Zulip server, and starts
the version corresponding to the `restart-server` path you call.

## Preserving local changes to configuration files

```eval_rst
.. warning::
    If you have modified configuration files installed by
    Zulip (e.g. the nginx configuration), the Zulip upgrade process will
    overwrite your configuration when it does the ``puppet apply``.
```

You can test whether this will happen assuming no upstream changes to
the configuration using `scripts/zulip-puppet-apply` (without the
`-f` option), which will do a test Puppet run and output and changes
it would make. Using this list, you can save a copy of any files
that you've modified, do the upgrade, and then restore your
configuration.

That said, Zulip's configuration files are designed to be flexible
enough for a wide range of installations, from a small self-hosted
system to Zulip Cloud.  Before making local changes to a configuration
file, first check whether there's an option supported by
`/etc/zulip/zulip.conf` for the customization you need.  And if you
need to make local modifications, please report the issue so that we
can make the Zulip Puppet configuration flexible enough to handle your
setup.

### nginx configuration changes

If you need to modify Zulip's `nginx` configuration, we recommend
first attempting to add configuration to `/etc/nginx/conf.d` or
`/etc/nginx/zulip-include/app.d`; those directories are designed for
custom configuration.

## Upgrading the operating system

When you upgrade the operating system on which Zulip is installed
(E.g. Ubuntu 18.04 Bionic to Ubuntu 20.04 Focal), you need to take
some additional steps to update your Zulip installation, documented
below.

The steps are largely the same for the various OS upgrades aside from
the versions of PostgreSQL, so you should be able to adapt these
instructions for other supported platforms.

### Upgrading from Ubuntu 18.04 Bionic to 20.04 Focal

1. Upgrade your server to the latest Zulip release (at least 3.0,
   which adds support for Ubuntu Focal).

2. As the Zulip user, stop the Zulip server and run the following
   to back up the system:

    ```
    supervisorctl stop all
    /home/zulip/deployments/current/manage.py backup --output=/home/zulip/release-upgrade.backup.tar.gz
    ```

3. Switch to the root user and upgrade the operating system using the
   OS's standard tooling.  E.g. for Ubuntu, this means running
   `do-release-upgrade` and following the prompts until it completes
   successfully:

    ```
    sudo -i # Or otherwise get a root shell
    do-release-upgrade -d
    ```

    The `-d` option to `do-release-upgrade` is required because Ubuntu
    20.04 is new; it will stop being necessary once the first point
    release update of Ubuntu 20.04 LTS is released.

    When `do-release-upgrade` asks you how to upgrade configuration
    files for services that Zulip manages like Redis, PostgreSQL,
    Nginx, and memcached, the best choice is `N` to keep the
    currently installed version.  But it's not important; the next
    step will re-install Zulip's configuration in any case.

4. As root, upgrade the database to the latest version of PostgreSQL:

    ```
    /home/zulip/deployments/current/scripts/setup/upgrade-postgresql
    ```

5. Finally, we need to reinstall the current version of Zulip, which
   among other things will recompile Zulip's Python module
   dependencies for your new version of Python and rewrite Zulip's
   full-text search indexes to work with the upgraded dictionary
   packages:

    ```
    rm -rf /srv/zulip-venv-cache/*
    /home/zulip/deployments/current/scripts/lib/upgrade-zulip-stage-2 \
        /home/zulip/deployments/current/ --ignore-static-assets --audit-fts-indexes
    ```

   This will finish by restarting your Zulip server; you should now be
   able to navigate to its URL and confirm everything is working
   correctly.

### Upgrading from Ubuntu 16.04 Xenial to 18.04 Bionic

1. Upgrade your server to the latest Zulip `2.1.x` release.  You can
   only upgrade to Zulip 3.0 and newer after completing this process,
   since newer releases don't support Ubuntu 16.04 Xenial.

2. Same as for Bionic to Focal.

3. Same as for Bionic to Focal.

4. As root, upgrade the database installation and OS configuration to
   match the new OS version:

    ```
    touch /usr/share/postgresql/10/pgroonga_setup.sql.applied
    /home/zulip/deployments/current/scripts/zulip-puppet-apply -f
    pg_dropcluster 10 main --stop
    systemctl stop postgresql
    pg_upgradecluster 9.5 main
    pg_dropcluster 9.5 main
    apt remove postgresql-9.5
    systemctl start postgresql
    systemctl restart memcached
    ```

5. Finally, we need to reinstall the current version of Zulip, which
   among other things will recompile Zulip's Python module
   dependencies for your new version of Python:

    ```
    rm -rf /srv/zulip-venv-cache/*
    /home/zulip/deployments/current/scripts/lib/upgrade-zulip-stage-2 \
        /home/zulip/deployments/current/ --ignore-static-assets
    ```

   This will finish by restarting your Zulip server; you should now
   be able to navigate to its URL and confirm everything is working
   correctly.

6. [Upgrade to the latest Zulip release](#upgrading-to-a-release), now
   that your server is running a supported operating system.

7. As root, finish by verifying the contents of the full-text indexes:

    ```
    /home/zulip/deployments/current/manage.py audit_fts_indexes
    ```

### Upgrading from Ubuntu 14.04 Trusty to 16.04 Xenial

1. Upgrade your server to the latest Zulip `2.0.x` release.  You can
   only upgrade to Zulip `2.1.x` and newer after completing this
   process, since newer releases don't support Ubuntu 14.04 Trusty.

2. Same as for Bionic to Focal.

3. Same as for Bionic to Focal.

4. As root, upgrade the database installation and OS configuration to
   match the new OS version:

    ```
    apt remove upstart -y
    /home/zulip/deployments/current/scripts/zulip-puppet-apply -f
    pg_dropcluster 9.5 main --stop
    systemctl stop postgresql
    pg_upgradecluster -m upgrade 9.3 main
    pg_dropcluster 9.3 main
    apt remove postgresql-9.3
    systemctl start postgresql
    service memcached restart
    ```

5. Finally, we need to reinstall the current version of Zulip, which
   among other things will recompile Zulip's Python module
   dependencies for your new version of Python:

    ```
    rm -rf /srv/zulip-venv-cache/*
    /home/zulip/deployments/current/scripts/lib/upgrade-zulip-stage-2 \
        /home/zulip/deployments/current/ --ignore-static-assets
    ```

   This will finish by restarting your Zulip server; you should now be
   able to navigate to its URL and confirm everything is working
   correctly.

6. [Upgrade from Xenial to
   Bionic](#upgrading-from-ubuntu-16-04-xenial-to-18-04-bionic), so
   that you are running a supported operating system.

### Upgrading from Debian Stretch to Debian Buster

1. Upgrade your server to the latest Zulip `2.1.x` release.  You can
   only upgrade to Zulip 3.0 and newer after completing this process,
   since newer releases don't support Ubuntu Debian Stretch.

2. Same as for Bionic to Focal.

3. Follow [Debian's instructions to upgrade the OS][debian-upgrade-os].

   [debian-upgrade-os]: https://www.debian.org/releases/buster/amd64/release-notes/ch-upgrading.html

   When prompted for you how to upgrade configuration
   files for services that Zulip manages like Redis, PostgreSQL,
   Nginx, and memcached, the best choice is `N` to keep the
   currently installed version.  But it's not important; the next
   step will re-install Zulip's configuration in any case.

4. As root, upgrade the database installation and OS configuration to
   match the new OS version:

    ```
    apt remove upstart -y
    /home/zulip/deployments/current/scripts/zulip-puppet-apply -f
    pg_dropcluster 11 main --stop
    systemctl stop postgresql
    pg_upgradecluster -m upgrade 9.6 main
    pg_dropcluster 9.6 main
    apt remove postgresql-9.6
    systemctl start postgresql
    service memcached restart
    ```

5. Finally, we need to reinstall the current version of Zulip, which
   among other things will recompile Zulip's Python module
   dependencies for your new version of Python:

    ```
    rm -rf /srv/zulip-venv-cache/*
    /home/zulip/deployments/current/scripts/lib/upgrade-zulip-stage-2 \
        /home/zulip/deployments/current/ --ignore-static-assets
    ```

   This will finish by restarting your Zulip server; you should now
   be able to navigate to its URL and confirm everything is working
   correctly.

6. [Upgrade to the latest Zulip release](#upgrading-to-a-release), now
   that your server is running a supported operating system.

7. As root, finish by verifying the contents of the full-text indexes:

    ```
    /home/zulip/deployments/current/manage.py audit_fts_indexes
    ```

## Upgrading PostgreSQL

Starting with Zulip 3.0, we use the latest available version of
PostgreSQL at installation time (currently version 12).  Upgrades to
the version of PostgreSQL are no longer linked to upgrades of the
distribution; that is, you may opt to upgrade to PostgreSQL 12 while
running Ubuntu 18.04 Bionic.

To upgrade the version of PostgreSQL on the Zulip server:

1. Upgrade your server to the latest Zulip release (at least 3.0).

2. Stop the server and take a backup:

    ```
    sudo -i # Or otherwise get a root shell
    supervisorctl stop all
    /home/zulip/deployments/current/manage.py backup --output=/home/zulip/postgresql-upgrade.backup.tar.gz
    ```

3. As root, run the database upgrade tool:

    ```
    /home/zulip/deployments/current/scripts/setup/upgrade-postgresql
    ```

`upgrade-postgresql` will have finished by restarting your Zulip server;
you should now be able to navigate to its URL and confirm everything
is working correctly.


## Modifying Zulip

Zulip is 100% free and open source software, and you're welcome to
modify it!  This section explains how to make and maintain
modifications in a safe and convenient fashion.

If you do modify Zulip and then report an issue you see in your
modified version of Zulip, please be responsible about communicating
that fact:

* Ideally, you'd reproduce the issue in an unmodified version (e.g. on
[chat.zulip.org](../contributing/chat-zulip-org.md) or
[zulip.com](https://zulip.com)).
* Where that is difficult or you think it's very unlikely your changes
are related to the issue, just mention your changes in the issue report.

If you're looking to modify Zulip by applying changes developed by the
Zulip core team and merged into master, skip to [this
section](#applying-changes-from-master).

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
  the Zulip development environment](../development/overview.md) on
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

* Log in to your Zulip server and configure and use
[upgrade-zulip-from-git][] to install the changes; remember to
configure `git_repo_url` to point to your fork on GitHub and run it as
`upgrade-zulip-from-git acme-branch`.

This workflow solves all of the problems described above: your change
will be compiled and installed correctly (restarting the server), and
your changes will be tracked so that it's convenient to maintain them
across future Zulip releases.

### Upgrading to future releases

Eventually, you'll want to upgrade to a new Zulip release.  If your
changes were integrated into that Zulip release or are otherwise no
longer needed, you can just [upgrade as
usual](#upgrading-to-a-release).  If you [upgraded to
master](#upgrading-to-master); review that section again; new
maintenance releases are likely "older" than your current installation
and you might need to upgrade to the master again rather than to the
new maintenance release.

Otherwise, you'll need to update your branch by rebasing your changes
(starting from a [clone][fork-clone] of the [zulip/zulip][]
repository).  The example below assumes you have a branch off of 2.0.4
and want to upgrade to 2.1.0.

```
cd zulip
git fetch --tags upstream
git checkout acme-branch
git rebase --onto 2.1.0 2.0.4
# Fix any errors or merge conflicts; see Zulip's Git guide for advice

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

In general, we can't provide unpaid support for issues caused by
cherry-picking arbitrary commits if the issues don't also affect
master or an official release.

The exception to this rule is when we ask or encourage a user to apply
a change to their production system to help verify the fix resolves
the issue for them.  You can expect the Zulip community to be
responsive in debugging any problems caused by a patch we asked
you to apply.

Also, consider asking whether a small fix that is important to you can
be added to the current stable release branch (E.g. `2.1.x`).  In
addition to scheduling that change for Zulip's next bug fix release,
we support changes in stable release branches as though they were
released.

### Upgrading to master

Many Zulip servers (including chat.zulip.org and zulip.com) upgrade to
master on a regular basis to get the latest features.  Before doing
so, it's important to understand how to happily run a server based on
master.

For background, it's backporting arbitrary patches from master to an
older version requires some care.  Common issues include:

* Changes containing database migrations (new files under
  `*/migrations/`), which includes most new features.  We
  don't support applying database migrations out of order.
* Changes that are stacked on top of other changes to the same system.
* Essentially any patch with hundreds of lines of changes will have
  merge conflicts and require extra work to apply.

While it's possible to backport these sorts of changes, you're
unlikely to succeed without help from the core team via a support
contract.

If you need an unreleased feature, the best path is usually to
upgrade to Zulip master using [upgrade-zulip-from-git][].  Before
upgrading to master, make sure you understand:

* In Zulip's version numbering scheme, `master` will always be "newer"
  than the latest maintenance release (E.g. `3.1` or `2.1.6`) and
  "older" than the next major release (E.g. `3.0` or `4.0`).
* The `master` branch is under very active development; dozens of new
  changes are integrated into it on most days.  The `master` branch
  can have thousands of changes not present in the latest release (all
  of which will be included in our next major release).  On average
  `master` usually has fewer total bugs than the latest release
  (because we fix hundreds of bugs in every major release) but it
  might have some bugs that are more severe than we would consider
  acceptable for a release.
* We deploy `master` to chat.zulip.org and zulip.com on a regular
  basis (often daily), so it's very important to the project that it
  be stable.  Most regressions will be minor UX issues or be fixed
  quickly, because we need them to be fixed for Zulip Cloud.
* The development community is very interested in helping debug issues
  that arise when upgrading from the latest release to master, since
  they provide us an opportunity to fix that category of issue before
  our next major release.  (Much more so than we are in helping folks
  debug other custom changes).  That said, we cannot make any
  guarantees about how quickly we'll resolve an issue to folks without
  a formal support contract.
* We do not support downgrading from `master` to earlier versions, so
  if downtime for your Zulip server is unacceptable, make sure you
  have a current
  [backup](../production/export-and-import.html#backups) in case the
  upgrade fails.
* Our changelog contains [draft release
  notes](../overview/changelog.md) available listing major changes
  since the last release.  The **Upgrade notes** section will always
  be current, even if some new features aren't documented.
* Whenever we push a security or maintenance release, the changes in
  that release will always be merged to master; so you can get the
  security fixes by upgrading to master.
* You can always upgrade from master to the next major release when it
  comes out, using either [upgrade-zulip-from-git][] or the release
  tarball.  So there's no risk of upgrading to `master` resulting in
  a system that's not upgradeable back to a normal release.

## Contributing patches

Zulip contains thousands of changes submitted by volunteer
contributors like you.  If your changes are likely to be of useful to
other organizations, consider [contributing
them](../overview/contributing.md).

[fork-clone]: ../git/cloning.html#get-zulip-code
[upgrade-zulip-from-git]: #upgrading-from-a-git-repository
[upgrade-zulip]: #upgrading
[git-guide]: ../git/index.md
[zulip/zulip]: https://github.com/zulip/zulip/
[docker-upgrade]: https://github.com/zulip/docker-zulip#upgrading-the-zulip-container
