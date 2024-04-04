# Upgrade Zulip

This page explains how to upgrade a Zulip server, including:

- [Upgrading to a release](#upgrading-to-a-release)
- [Upgrading from a Git repository](#upgrading-from-a-git-repository)
- [Updating `settings.py` inline documentation](#updating-settingspy-inline-documentation)
- [Troubleshooting and rollback](#troubleshooting-and-rollback)
- [Preserving local changes to service configuration files](#preserving-local-changes-to-service-configuration-files)
- [Upgrading the operating system](#upgrading-the-operating-system)
- [Upgrading PostgreSQL](#upgrading-postgresql)

## Upgrading to a release

Note that there are additional instructions if you're [using
docker-zulip][docker-upgrade], have [patched Zulip](modify.md),
or have [modified Zulip-managed configuration
files](#preserving-local-changes-to-service-configuration-files). To upgrade
to a new Zulip release:

1. Read the [upgrade notes](../overview/changelog.md#upgrade-notes)
   for all releases newer than what is currently installed.

1. Download the appropriate release tarball from
   <https://download.zulip.com/server/>. You can get the latest
   release (**Zulip Server {{ LATEST_RELEASE_VERSION }}**) with the
   following command:

   ```bash
   curl -fLO https://download.zulip.com/server/zulip-server-latest.tar.gz
   ```

   You also have the option of upgrading Zulip [to a version in a Git
   repository directly](#upgrading-from-a-git-repository) or creating
   your own release tarballs from a copy of the [zulip.git
   repository](https://github.com/zulip/zulip) using
   `tools/build-release-tarball`.

1. Log in to your Zulip and run as root:

   ```bash
   /home/zulip/deployments/current/scripts/upgrade-zulip zulip-server-latest.tar.gz
   ```

   The upgrade process will:

   - Run `apt-get upgrade`
   - Install new versions of Zulip's dependencies (mainly Python packages).
   - (`upgrade-zulip-from-git` only) Build Zulip's frontend assets using `webpack`.
   - Shut down the Zulip service
   - Run a `puppet apply`
   - Run any database migrations
   - Bring the Zulip service back up on the new version.

Upgrading will result in brief downtime for the service, which should
be under 30 seconds unless there is an expensive database migration
involved (these will be documented in the [release
notes](../overview/changelog.md), and usually can be avoided with
some care). If downtime is problematic for your organization,
consider testing the upgrade on a
[backup](export-and-import.md#backups) in advance,
doing the final upgrade at off hours, or buying a support contract.

See the [troubleshooting guide](#troubleshooting-and-rollback) if you
run into any issues or need to roll back the upgrade.

After you have completed the Zulip upgrade, you may also wish to [upgrade the
version of PostgreSQL](#upgrading-postgresql).

## Upgrading from a Git repository

Zulip supports upgrading a production installation to any commit in a
Git repository, which is great for [running pre-release changes from
`main`](modify.md#applying-changes-from-main) or [maintaining a
fork](modify.md#making-changes). The process is simple:

```bash
# Upgrade to an official release
/home/zulip/deployments/current/scripts/upgrade-zulip-from-git 1.8.1
# Upgrade to a branch (or other Git ref)
/home/zulip/deployments/current/scripts/upgrade-zulip-from-git 2.1.x
/home/zulip/deployments/current/scripts/upgrade-zulip-from-git main
```

Zulip will automatically fetch the relevant Git commit and upgrade to
that version of Zulip.

Branches with names like `2.1.x` are stable release branches,
containing the changes planned for the next minor release
(E.g. 2.1.5); we support these stable release branches as though they
were a published release.

The `main` branch contains changes planned for the next major
release (E.g. 3.0); see our documentation on [running
`main`](modify.md#upgrading-to-main) before upgrading to it.

By default, this uses the main upstream Zulip server repository, but
you can configure any other Git repository by adding a section like
this to `/etc/zulip/zulip.conf`:

```ini
[deployment]
git_repo_url = https://github.com/zulip/zulip.git
```

See also our documentation on [upgrading
docker-zulip](https://github.com/zulip/docker-zulip#upgrading-from-a-git-repository).

## Updating `settings.py` inline documentation

Zulip installations often upgrade many times over their lifetime, and
we strive to keep all configuration files backwards-compatible.
However, our practice of leaving the `/etc/zulip/settings.py`
unchanged during upgrades means that there may be new features which
are not documented in that file, since it was based on a template
provided by an earlier version of Zulip, during the initial install.

After upgrading across major versions of Zulip Server, we recommend
comparing your `/etc/zulip/settings.py` file to the current settings
template, which can be found in
`/home/zulip/deployments/current/zproject/prod_settings_template.py`. We
suggest using that updated template to update
`/etc/zulip/settings.py`:

1. Copy the current `settings.py` to make a backup (especially if you
   do not have a recent [complete backup][backups]), and make a copy
   of the current template:

   ```bash
   cp -a /etc/zulip/settings.py ~/zulip-settings-backup.py
   cp -a /home/zulip/deployments/current/zproject/prod_settings_template.py /etc/zulip/settings-new.py
   ```

1. Open both `/etc/zulip/settings.py` and `/etc/zulip/settings-new.py`
   files in an editor; for each setting set in `settings.py`, find its
   section in `/etc/zulip/settings-new.py` and copy the setting from
   `settings.py` into there.

   The following tool may help, by finding the most likely version of
   the template that your `/etc/zulip/settings.py` was installed
   using, and the differences that your file has from that:

   ```bash
   /home/zulip/deployments/current/scripts/setup/compare-settings-to-template
   ```

   If there are settings which you cannot find documented in
   `/etc/zulip/settings-new.py`, check the [changelog][changelog] to see
   if they have been removed.

1. Overwrite the configuration with the updated file, and restart the
   server to pick up the updates; this should be a no-op, but it is
   much better to discover immediately if it is not:

   ```bash
   cp -a /etc/zulip/settings-new.py /etc/zulip/settings.py
   su zulip -c '/home/zulip/deployments/current/scripts/restart-server'
   ```

[backups]: export-and-import.md#backups
[changelog]: ../overview/changelog.md

## Troubleshooting and rollback

See also the general Zulip server [troubleshooting
guide](troubleshooting.md).

The upgrade scripts are idempotent, so there's no harm in trying again
after resolving an issue. The most common causes of errors are:

- Networking issues (e.g. your Zulip server doesn't have reliable
  Internet access or needs a proxy set up). Fix the networking issue
  and try again.
- Especially when using `upgrade-zulip-from-git`, systems with the
  minimal RAM for running Zulip can run into out-of-memory issues
  during the upgrade process (generally `tools/webpack` is the step
  that fails). You can get past this by shutting down the Zulip
  server with `./scripts/stop-server` to free up RAM before running
  the upgrade process.

Useful logs are available in a few places:

- The Zulip upgrade scripts log all output to
  `/var/log/zulip/upgrade.log`.
- The Zulip server logs all Internal Server Errors to
  `/var/log/zulip/errors.log`.

If you need help and don't have a support contract, you can visit
[#production
help](https://chat.zulip.org/#narrow/stream/31-production-help) in the
[Zulip development community
server](https://zulip.com/development-community/) for best-effort help.
Please include the relevant error output from the above logs in a
[Markdown code
block](https://zulip.com/help/code-blocks)
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
`/home/zulip/deployments/DATE/scripts/restart-server`. The
`restart-server` script stops any running Zulip server, and starts
the version corresponding to the `restart-server` path you call.

## Deployment hooks

Zulip's upgrades have a hook system which allows for arbitrary
user-configured actions to run before and after an upgrade.

Files in the `/etc/zulip/pre-deploy.d` and `/etc/zulip/post-deploy.d`
directories are inspected for files ending with `.hook`, just before and after
the critical period when the server is restarted. Each file is called, sorted in
alphabetical order, from the working directory of the new version, with
environment variables as described below. If any of them exit with non-0 exit
code, the upgrade will abort.

The hook is run with the following environment variables set:

- `ZULIP_OLD_VERSION`: The version being upgraded from, which may either be a
  release name (e.g. `7.0` or `7.0-beta3`) or the output from `git describe`
  (e.g. `7.0-beta3-2-gdc158b18f2`).
- `ZULIP_NEW_VERSION`: The version being upgraded to, in the same format as
  `ZULIP_OLD_VERSION`.

If the upgrade is upgrading between [versions in `git`][upgrade-from-git], then
the following environment variables will also be present:

- `ZULIP_OLD_COMMIT`: The full commit hash of the version being upgraded from
- `ZULIP_NEW_COMMIT`: The full commit hash of the version being upgraded to
- `ZULIP_OLD_MERGE_BASE_COMMIT`: The full commit hash of the merge-base of the
  version being upgraded from, and the public branch in
  [`zulip/zulip`][zulip/zulip]. This will be the closest commit in standard
  Zulip Server to the version being upgraded from.
- `ZULIP_NEW_MERGE_BASE_COMMIT`: The full commit hash of the merge-base of the
  version being upgraded to, and the public branch in
  [`zulip/zulip`][zulip/zulip]. This will be the closest commit in standard
  Zulip Server to the version being upgraded to.

See the [deploy documentation](deployment.md#deployment-hooks) for
hooks included with Zulip.

[upgrade-from-git]: #upgrading-from-a-git-repository
[zulip/zulip]: https://github.com/zulip/zulip/

## Preserving local changes to service configuration files

:::{warning}
If you have modified service configuration files installed by
Zulip (e.g. the nginx configuration), the Zulip upgrade process will
overwrite your configuration when it does the `puppet apply`.
:::

You can test whether this will happen assuming no upstream changes to
the configuration using `scripts/zulip-puppet-apply` (without the
`-f` option), which will do a test Puppet run and output and changes
it would make. Using this list, you can save a copy of any files
that you've modified, do the upgrade, and then restore your
configuration.

That said, Zulip's configuration files are designed to be flexible
enough for a wide range of installations, from a small self-hosted
system to Zulip Cloud. Before making local changes to a configuration
file, first check whether there's an option supported by
`/etc/zulip/zulip.conf` for the customization you need. And if you
need to make local modifications, please report the issue so that we
can make the Zulip Puppet configuration flexible enough to handle your
setup.

### nginx configuration changes

If you need to modify Zulip's `nginx` configuration, we recommend
first attempting to add configuration to `/etc/nginx/conf.d` or
`/etc/nginx/zulip-include/app.d`; those directories are designed for
custom configuration, and are not overridden during upgrades. The
former is useful for directives with the `http` [context][context],
and the latter for `server` contexts.

[context]: http://nginx.org/en/docs/beginners_guide.html#conf_structure

## Upgrading the operating system

When you upgrade the operating system on which Zulip is installed
(E.g. Ubuntu 20.04 Focal to Ubuntu 22.04 Jammy), you need to take
some additional steps to update your Zulip installation, documented
below.

The steps are largely the same for the various OS upgrades aside from
the versions of PostgreSQL, so you should be able to adapt these
instructions for other supported platforms.

### Upgrading from Ubuntu 20.04 Focal to 22.04 Jammy

1. Upgrade your server to the latest Zulip `5.x` release (at
   least 5.3, which adds support for Ubuntu 22.04 and above).

2. As the Zulip user, stop the Zulip server and run the following
   to back up the system:

   ```bash
   supervisorctl stop all
   /home/zulip/deployments/current/manage.py backup --output=/home/zulip/release-upgrade.backup.tar.gz
   ```

3. Switch to the root user and upgrade the operating system using the
   OS's standard tooling. E.g. for Ubuntu, this means running
   `do-release-upgrade` and following the prompts until it completes
   successfully:

   ```bash
   sudo -i # Or otherwise get a root shell
   do-release-upgrade
   ```

   When `do-release-upgrade` asks you how to upgrade configuration
   files for services that Zulip manages like Redis, PostgreSQL,
   nginx, and memcached, the best choice is `N` to keep the
   currently installed version. But it's not important; the next
   step will re-install Zulip's configuration in any case.

4. As root, upgrade the database to the latest version of PostgreSQL:

   ```bash
   /home/zulip/deployments/current/scripts/setup/upgrade-postgresql
   ```

5. Next, we need to reinstall the current version of Zulip, which
   among other things will recompile Zulip's Python module
   dependencies for your new version of Python and rewrite Zulip's
   full-text search indexes to work with the upgraded dictionary
   packages:

   ```bash
   rm -rf /srv/zulip-venv-cache/*
   /home/zulip/deployments/current/scripts/lib/upgrade-zulip-stage-2 \
       /home/zulip/deployments/current/ --ignore-static-assets --audit-fts-indexes
   ```

   This will finish by restarting your Zulip server; you should now be
   able to navigate to its URL and confirm everything is working
   correctly.

### Upgrading from Ubuntu 18.04 Bionic to 20.04 Focal

1. Upgrade your server to the latest Zulip `3.x` or `4.x` release (at
   least 3.0, which adds support for Ubuntu 20.04). You can only
   upgrade to Zulip 5.0 and newer after completing this process, since
   newer releases don't support Ubuntu 18.04.

2. As the Zulip user, stop the Zulip server and run the following
   to back up the system:

   ```bash
   supervisorctl stop all
   /home/zulip/deployments/current/manage.py backup --output=/home/zulip/release-upgrade.backup.tar.gz
   ```

3. Switch to the root user and upgrade the operating system using the
   OS's standard tooling. E.g. for Ubuntu, this means running
   `do-release-upgrade` and following the prompts until it completes
   successfully:

   ```bash
   sudo -i # Or otherwise get a root shell
   do-release-upgrade
   ```

   When `do-release-upgrade` asks you how to upgrade configuration
   files for services that Zulip manages like Redis, PostgreSQL,
   nginx, and memcached, the best choice is `N` to keep the
   currently installed version. But it's not important; the next
   step will re-install Zulip's configuration in any case.

4. As root, upgrade the database to the latest version of PostgreSQL:

   ```bash
   /home/zulip/deployments/current/scripts/setup/upgrade-postgresql
   ```

5. Next, we need to reinstall the current version of Zulip, which
   among other things will recompile Zulip's Python module
   dependencies for your new version of Python and rewrite Zulip's
   full-text search indexes to work with the upgraded dictionary
   packages:

   ```bash
   rm -rf /srv/zulip-venv-cache/*
   /home/zulip/deployments/current/scripts/lib/upgrade-zulip-stage-2 \
       /home/zulip/deployments/current/ --ignore-static-assets --audit-fts-indexes
   ```

   This will finish by restarting your Zulip server; you should now be
   able to navigate to its URL and confirm everything is working
   correctly.

6. Finally, Ubuntu 20.04 has a different version of the low-level
   glibc library, which affects how PostgreSQL orders text data (known
   as "collations"); this corrupts database indexes that rely on
   collations. Regenerate the affected indexes by running:

   ```bash
   /home/zulip/deployments/current/scripts/setup/reindex-textual-data --force
   ```

7. [Upgrade from Ubuntu 20.04 to
   22.04](#upgrading-from-ubuntu-2004-focal-to-2204-jammy), so that
   you are running a supported operating system.

### Upgrading from Ubuntu 16.04 Xenial to 18.04 Bionic

1. Upgrade your server to the latest Zulip `2.1.x` release. You can
   only upgrade to Zulip 3.0 and newer after completing this process,
   since newer releases don't support Ubuntu 16.04 Xenial.

2. Same as for Ubuntu 18.04 to 20.04.

3. Same as for Ubuntu 18.04 to 20.04.

4. As root, upgrade the database installation and OS configuration to
   match the new OS version:

   ```bash
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

   ```bash
   rm -rf /srv/zulip-venv-cache/*
   /home/zulip/deployments/current/scripts/lib/upgrade-zulip-stage-2 \
       /home/zulip/deployments/current/ --ignore-static-assets
   ```

   This will finish by restarting your Zulip server; you should now
   be able to navigate to its URL and confirm everything is working
   correctly.

6. [Upgrade to the latest `4.x` release](#upgrading-to-a-release).

7. As root, verify the contents of the full-text indexes:

   ```bash
   /home/zulip/deployments/current/manage.py audit_fts_indexes
   ```

8. [Upgrade from Ubuntu 18.04 to
   20.04](#upgrading-from-ubuntu-1804-bionic-to-2004-focal), the next
   in chain of upgrades leading to a supported operating system.

### Upgrading from Ubuntu 14.04 Trusty to 16.04 Xenial

1. Upgrade your server to the latest Zulip `2.0.x` release. You can
   only upgrade to Zulip `2.1.x` and newer after completing this
   process, since newer releases don't support Ubuntu 14.04 Trusty.

2. Same as for Ubuntu 18.04 to 20.04.

3. Same as for Ubuntu 18.04 to 20.04.

4. As root, upgrade the database installation and OS configuration to
   match the new OS version:

   ```bash
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

   ```bash
   rm -rf /srv/zulip-venv-cache/*
   /home/zulip/deployments/current/scripts/lib/upgrade-zulip-stage-2 \
       /home/zulip/deployments/current/ --ignore-static-assets
   ```

   This will finish by restarting your Zulip server; you should now be
   able to navigate to its URL and confirm everything is working
   correctly.

6. [Upgrade from Ubuntu 16.04 to
   18.04](#upgrading-from-ubuntu-1604-xenial-to-1804-bionic), the next
   in chain of upgrades leading to a supported operating system.

### Upgrading from Debian 11 to 12

1. Upgrade your server to the latest `7.x` release.

2. As the Zulip user, stop the Zulip server and run the following
   to back up the system:

   ```bash
   /home/zulip/deployments/current/scripts/stop-server
   /home/zulip/deployments/current/manage.py backup --output=/home/zulip/release-upgrade.backup.tar.gz
   ```

3. Follow [Debian's instructions to upgrade the OS][bookworm-upgrade].

   [bookworm-upgrade]: https://www.debian.org/releases/bookworm/amd64/release-notes/ch-upgrading.html

   When prompted for you how to upgrade configuration
   files for services that Zulip manages like Redis, PostgreSQL,
   nginx, and memcached, the best choice is `N` to keep the
   currently installed version. But it's not important; the next
   step will re-install Zulip's configuration in any case.

4. As root, run the following steps to regenerate configurations
   for services used by Zulip:

   ```bash
   apt remove upstart -y
   /home/zulip/deployments/current/scripts/zulip-puppet-apply -f
   ```

5. Reinstall the current version of Zulip, which among other things
   will recompile Zulip's Python module dependencies for your new
   version of Python:

   ```bash
   rm -rf /srv/zulip-venv-cache/*
   /home/zulip/deployments/current/scripts/lib/upgrade-zulip-stage-2 \
       /home/zulip/deployments/current/ --ignore-static-assets --audit-fts-indexes
   ```

   This will finish by restarting your Zulip server; you should now
   be able to navigate to its URL and confirm everything is working
   correctly.

6. As an additional step, you can also [upgrade the PostgreSQL version](#upgrading-postgresql).

### Upgrading from Debian 10 to 11

1. Upgrade your server to the latest `5.x` release. You can only
   upgrade to Zulip Server 6.0 and newer after completing this
   process, since newer releases don't support Debian 10.

2. As the Zulip user, stop the Zulip server and run the following
   to back up the system:

   ```bash
   /home/zulip/deployments/current/scripts/stop-server
   /home/zulip/deployments/current/manage.py backup --output=/home/zulip/release-upgrade.backup.tar.gz
   ```

3. Follow [Debian's instructions to upgrade the OS][bullseye-upgrade].

   [bullseye-upgrade]: https://www.debian.org/releases/bullseye/amd64/release-notes/ch-upgrading.html

   When prompted for you how to upgrade configuration
   files for services that Zulip manages like Redis, PostgreSQL,
   nginx, and memcached, the best choice is `N` to keep the
   currently installed version. But it's not important; the next
   step will re-install Zulip's configuration in any case.

4. As root, run the following steps to regenerate configurations
   for services used by Zulip:

   ```bash
   apt remove upstart -y
   /home/zulip/deployments/current/scripts/zulip-puppet-apply -f
   ```

5. Reinstall the current version of Zulip, which among other things
   will recompile Zulip's Python module dependencies for your new
   version of Python:

   ```bash
   rm -rf /srv/zulip-venv-cache/*
   /home/zulip/deployments/current/scripts/lib/upgrade-zulip-stage-2 \
       /home/zulip/deployments/current/ --ignore-static-assets --audit-fts-indexes
   ```

   This will finish by restarting your Zulip server; you should now
   be able to navigate to its URL and confirm everything is working
   correctly.

6. Debian 11 has a different version of the low-level glibc
   library, which affects how PostgreSQL orders text data (known as
   "collations"); this corrupts database indexes that rely on
   collations. Regenerate the affected indexes by running:

   ```bash
   /home/zulip/deployments/current/scripts/setup/reindex-textual-data --force
   ```

7. As an additional step, you can also [upgrade the PostgreSQL version](#upgrading-postgresql).

8. [Upgrade from Debian 11 to 12](#upgrading-from-debian-11-to-12),
   so that you are running a supported operating system.

### Upgrading from Debian 9 to 10

1. Upgrade your server to the latest Zulip `2.1.x` release. You can
   only upgrade to Zulip 3.0 and newer after completing this process,
   since newer releases don't support Debian 9.

2. As the Zulip user, stop the Zulip server and run the following
   to back up the system:

   ```bash
   supervisorctl stop all
   /home/zulip/deployments/current/manage.py backup --output=/home/zulip/release-upgrade.backup.tar.gz
   ```

3. Follow [Debian's instructions to upgrade the OS][debian-upgrade-os].

   [debian-upgrade-os]: https://www.debian.org/releases/buster/amd64/release-notes/ch-upgrading.html

   When prompted for you how to upgrade configuration
   files for services that Zulip manages like Redis, PostgreSQL,
   nginx, and memcached, the best choice is `N` to keep the
   currently installed version. But it's not important; the next
   step will re-install Zulip's configuration in any case.

4. As root, upgrade the database installation and OS configuration to
   match the new OS version:

   ```bash
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

   ```bash
   rm -rf /srv/zulip-venv-cache/*
   /home/zulip/deployments/current/scripts/lib/upgrade-zulip-stage-2 \
       /home/zulip/deployments/current/ --ignore-static-assets
   ```

   This will finish by restarting your Zulip server; you should now
   be able to navigate to its URL and confirm everything is working
   correctly.

6. [Upgrade to the latest `5.x` release](#upgrading-to-a-release), now
   that your server is running a supported operating system.

7. Debian 10 has a different version of the low-level glibc
   library, which affects how PostgreSQL orders text data (known as
   "collations"); this corrupts database indexes that rely on
   collations. Regenerate the affected indexes by running:

   ```bash
   /home/zulip/deployments/current/scripts/setup/reindex-textual-data --force
   ```

8. As root, finish by verifying the contents of the full-text indexes:

   ```bash
   /home/zulip/deployments/current/manage.py audit_fts_indexes
   ```

9. [Upgrade from Debian 10 to 11](#upgrading-from-debian-10-to-11),
   the next in chain of upgrades leading to a supported operating
   system.

## Upgrading PostgreSQL

Starting with Zulip 3.0, we use the latest available version of
PostgreSQL at installation time (currently version 16). Upgrades to
the version of PostgreSQL are no longer linked to upgrades of the
distribution; that is, you may opt to upgrade to PostgreSQL 16 while
running Ubuntu 22.04.

Not all versions of Zulip Server support all versions of PostgreSQL, however:

```{include} postgresql-support-table.md

```

To upgrade the version of PostgreSQL on the Zulip server:

1. Upgrade your server to the latest Zulip release (at least 3.0).

1. Stop the server, as the `zulip` user:

   ```bash
   # On Zulip before 4.0, use `supervisor stop all` instead
   /home/zulip/deployments/current/scripts/stop-server
   ```

1. Take a backup, in case of any problems:

   ```bash
   /home/zulip/deployments/current/manage.py backup --output=/home/zulip/postgresql-upgrade.backup.tar.gz
   ```

1. As root, run the database upgrade tool:

   ```bash
   /home/zulip/deployments/current/scripts/setup/upgrade-postgresql
   ```

1. As the `zulip` user, start the server again:

   ```bash
   # On Zulip before 4.0, use `restart-server` instead of `start-server` instead
   /home/zulip/deployments/current/scripts/start-server
   ```

You should now be able to navigate to the Zulip server's URL and
confirm everything is working correctly.

[docker-upgrade]: https://github.com/zulip/docker-zulip#upgrading-the-zulip-container
