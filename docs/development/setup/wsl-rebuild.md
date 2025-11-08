If you ever want to recreate your development environment again from
scratch (e.g., to test a change you've made to the provisioning
process, or because you think something is broken), you can do so
using the following steps:

1. To find the distribution name to unregister (delete), open Command
   Prompt or PowerShell and use the following command:

```console
$ wsl --list --verbose
```

If you are unsure about which distribution to unregister, you can log
into the WSL distributions to ensure you are deleting the one
containing your development environment using the command:

```console
wsl -d <Distribution Name>
```

2. To uninstall your WSL distribution, enter the command:

```console
$ wsl --unregister <Distribution Name>
```

For more information, checkout the [official documentation for WSL
commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands#unregister-or-uninstall-a-linux-distribution)

3. **Next, follow the setup instructions**, starting from [[Step 1:
Install
prerequisites]](/development/setup-recommended.md#step-1-install-prerequisites)

If you just want to rebuild the development database, the following is
much faster:

```console
$ ./tools/rebuild-dev-database
```

For more details, see the [schema migration
documentation](/subsystems/schema-migrations.md#schema-and-initial-data-changes).
