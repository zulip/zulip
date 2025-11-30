This directory contains scripts that:

- Generally do not require access to Django or the database (those are
  "management commands"), and thus are suitable to run operationally.

- Are useful for managing a production deployment of Zulip (many are
  also used in a Zulip development environment, though
  development-only scripts live in `tools/`).

For more details, see
https://zulip.readthedocs.io/en/latest/overview/directory-structure.html.

## Uninstallation

To uninstall Zulip:

```bash
sudo ./scripts/setup/uninstall [options]
```

Run with `--help` for options. The script can restore backed-up nginx configs
and remove Zulip files. Note that it doesn't remove PostgreSQL databases to
prevent data loss.
