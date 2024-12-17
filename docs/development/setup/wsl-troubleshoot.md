Below you'll find a list of common errors and their solutions. Most
issues are resolved by just provisioning again (by running
`./tools/provision` (from `/srv/zulip`) inside the WSL2 environment.

If these solutions aren't working for you or you encounter an issue not
documented below, there are a few ways to get further help:

- Ask in [#provision help](https://chat.zulip.org/#narrow/channel/21-provision-help)
  in the [Zulip development community server](https://zulip.com/development-community/).
- [File an issue](https://github.com/zulip/zulip/issues).

When reporting your issue, please include the following information:

- host operating system
- installation method (WSL2 in this case)
- whether or not you are using a proxy
- a copy of Zulip's provisioning logs, available in
  `/var/log/provision.log` on your virtual machine. If you choose to
  post just the error output, please include the **beginning of the
  error output**, not just the last few lines.

The output of `tools/diagnose` run inside the WSL instance is also
usually helpful.

WSL2 users often encounter issues where services fail to start or remain inactive. Follow the steps below to diagnose and resolve such problems.

## 1. Check the Status of the Service

To verify if a service is running, use the following command:

```console
$ systemctl status <service_name>
```

If the service is inactive, you can attempt to start it with:

```console
$ systemctl start <service_name>
```

## 2. Diagnose Port Conflicts

Services like `postgresql` may fail to start due to port conflicts. These conflicts can be caused by:

- Other services running in Windows.
- Services running in another WSL2 instance.

### Resolving Port Conflicts with Other WSL Instances

To resolve port conflicts with another WSL2 instance, stop the conflicting instance using the following command:

```console
> wsl -t <WSL_Instance_Name>
```

After stopping the conflicting instance, restart your WSL instance with:

```console
> wsl -d <Your_Zulip_Instance_Name>
```

### Resolving Port Conflicts with Services Running on Windows

To resolve conflicts caused by Windows processes:

1. Identify the process using the conflicting port by running:

```console
> Get-Process -Id (Get-NetTCPConnection -LocalPort <your_port_number>).OwningProcess
```

2. If a process is found, terminate it using:

```console
> taskkill /PID <pid> /F
```

## 3. Restart the Service or Enable Auto-Start

After resolving port conflicts, try restarting the service using:

```console
$ systemctl start <service_name>
```

To ensure the service always starts on boot, enable it with:

```console
$ systemctl enable <service_name>
```

---

## Additional Tips

- Use `wsl --list` to view all running WSL2 instances and their states.
- Avoid overlapping port usage between WSL2 instances and Windows processes.
- Keep a record of services and their associated port numbers to prevent conflicts in the future.
- Ensure that you use a fresh WSL instance to setup the Zulip development environment to avoid dependency conflicts.
