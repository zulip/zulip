WSL2 users may encounter issues where services fail to start or remain inactive. This guide outlines common causes and steps to diagnose and resolve them.

---

## 1. Check the status of a service

To verify whether a service is running:

```console
$ systemctl status <service_name>
```

If the service is inactive, attempt to start it:

```console
$ systemctl start <service_name>
```

If the service fails to start, carefully review the error output before proceeding.

---

## 2. Diagnose port conflicts

Services such as `postgresql` may fail to start due to port conflicts. These conflicts usually occur because:

- A Windows process is using the same port.
- Another WSL2 instance is running a service on that port.

---

### Resolving port conflicts with another WSL instance

List currently running WSL instances:

```console
> wsl --list --running
```

Stop the conflicting instance:

```console
> wsl -t <WSL_Instance_Name>
```

Restart your Zulip instance:

```console
> wsl -d <Your_Zulip_Instance_Name>
```

---

### Resolving port conflicts with Windows processes

1. Identify the process using the conflicting port:

```console
> Get-Process -Id (Get-NetTCPConnection -LocalPort <port_number>).OwningProcess
```

2. If a process is found, terminate it:

```console
> taskkill /PID <pid> /F
```

3. Restart the service inside WSL:

```console
$ systemctl start <service_name>
```

To ensure the service starts automatically on boot:

```console
$ systemctl enable <service_name>
```

---

## 3. Common onboarding issues during initial WSL setup

### Restart required after enabling WSL

After running `wsl --install` or manually enabling the `VirtualMachinePlatform` feature, a full system restart is required before launching Ubuntu for the first time.

If the system is not restarted, the distribution may fail to initialize properly.

---

### Running commands without Administrator privileges

If you see an error such as:

```console
The requested operation requires elevation
```

Make sure PowerShell or Command Prompt is opened as Administrator when running `wsl --install` or related setup commands.

---

### Cloning inside OneDrive-managed directories

Cloning the Zulip repository inside OneDrive-synced folders (e.g., Desktop or Documents) may cause file permission issues and provisioning failures.

It is recommended to clone inside the WSL home directory instead:

```console
$ cd ~
$ git clone https://github.com/zulip/zulip.git
```

---

### Verifying that you are inside WSL

Your shell prompt should look similar to:

```console
username@DESKTOP:~$
```

If you see a Windows-style path such as `C:\Users\...`, you are not inside the WSL environment.

---

### DNS resolution failures during `wsl --list --online`

Errors such as:

```console
Failed to fetch the list distribution
Wsl/WININET_E_NAME_NOT_RESOLVED
```

Indicate a network or DNS configuration issue in Windows. Verify that internet connectivity is working and that DNS resolution is functioning correctly on the host system.

---

## Additional tips

- Use `wsl --list` to view all WSL instances and their states.
- Avoid overlapping port usage between WSL instances and Windows processes.
- When setting up Zulip, prefer using a fresh WSL instance to prevent dependency conflicts.
- If services repeatedly fail, fully shut down WSL and restart:

```console
> wsl --shutdown
```