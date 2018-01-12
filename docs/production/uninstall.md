# Clean uninstall of Production Installation

Steps to wipe out an existing Zulip installation from a dedicated server or a
server running other web-apps:
1. If the supervisor socket `/var/run/supervisor.sock` exists, run
   `supervisorctl stop all`
2. (Optional) Drop the zulip database from postgres
   ```
   su "$POSTGRES" -c psql <<EOF
   CREATE USER zulip;
   ALTER ROLE zulip SET search_path TO zulip,public;
   DROP DATABASE IF EXISTS zulip;
   EOF
   ```
   Where `POSTGRES_USER` is by default `postgres`.
   This step is not required for a reinstall since the installation script also
   drops the zulip database before initializing a new one.
   Note: this is extracted from `./scripts/setup/postgres-init-db`
3. Remove (almost) all the files created by Zulip
   `rm -rf /etc/zulip /var/log/zulip /home/zulip/* /srv/zulip-*`
   Note: Some of Puppet-generated files are not removed since they don't take
   that much disk space, don't interfere with non-Zulip processes, and won't
   affect future Zulip installation since they are being generated in an
   idempotent way.
