#### Vagrant was unable to mount VirtualBox shared folders

For the following error:

```console
Vagrant was unable to mount VirtualBox shared folders. This is usually
because the filesystem "vboxsf" is not available. This filesystem is
made available via the VirtualBox Guest Additions and kernel
module. Please verify that these guest additions are properly
installed in the guest. This is not a bug in Vagrant and is usually
caused by a faulty Vagrant box. For context, the command attempted
was:

 mount -t vboxsf -o uid=1000,gid=1000 keys /keys
```

If this error starts happening unexpectedly, then just run:

```console
$ vagrant halt
$ vagrant up
```

to reboot the guest. After this, you can do `vagrant provision` and
`vagrant ssh`.

#### os.symlink error

If you receive the following error while running `vagrant up`:

```console
==> default: Traceback (most recent call last):
==> default: File "./emoji_dump.py", line 75, in <module>
==> default:
==> default: os.symlink('unicode/{}.png'.format(code_point), 'out/{}.png'.format(name))
==> default: OSError
==> default: :
==> default: [Errno 71] Protocol error
```

Then Vagrant was not able to create a symbolic link.

First, if you are using Windows, **make sure you have run Git BASH (or
Cygwin) as an administrator**. By default, only administrators can
create symbolic links on Windows. Additionally [UAC][windows-uac], a
Windows feature intended to limit the impact of malware, can prevent
even administrator accounts from creating symlinks. [Turning off
UAC][disable-uac] will allow you to create symlinks. You can also try
some of the solutions mentioned
[here](https://superuser.com/questions/124679/how-do-i-create-a-link-in-windows-7-home-premium-as-a-regular-user).

[windows-uac]: https://docs.microsoft.com/en-us/windows/security/identity-protection/user-account-control/how-user-account-control-works
[disable-uac]: https://stackoverflow.com/questions/15320550/why-is-secreatesymboliclinkprivilege-ignored-on-windows-8

If you ran Git BASH as administrator but you already had VirtualBox
running, you might still get this error because VirtualBox is not
running as administrator. In that case: close the Zulip VM with
`vagrant halt`; close any other VirtualBox VMs that may be running;
exit VirtualBox; and try again with `vagrant up --provision` from a
Git BASH running as administrator.

Second, VirtualBox does not enable symbolic links by default. Vagrant
starting with version 1.6.0 enables symbolic links for VirtualBox shared
folder.

You can check to see that this is enabled for your virtual machine with
`vboxmanage` command.

Get the name of your virtual machine by running `vboxmanage list vms` and
then print out the custom settings for this virtual machine with
`vboxmanage getextradata YOURVMNAME enumerate`:

```console
$ vboxmanage list vms
"zulip_default_1462498139595_55484" {5a65199d-8afa-4265-b2f6-6b1f162f157d}

$ vboxmanage getextradata zulip_default_1462498139595_55484 enumerate
Key: VBoxInternal2/SharedFoldersEnableSymlinksCreate/srv_zulip, Value: 1
Key: supported, Value: false
```

If you see "command not found" when you try to run VBoxManage, you need to
add the VirtualBox directory to your path. On Windows this is mostly likely
`C:\Program Files\Oracle\VirtualBox\`.

If `vboxmanage enumerate` prints nothing, or shows a value of 0 for
VBoxInternal2/SharedFoldersEnableSymlinksCreate/srv_zulip, then enable
symbolic links by running this command in Terminal/Git BASH/Cygwin:

```console
$ vboxmanage setextradata YOURVMNAME VBoxInternal2/SharedFoldersEnableSymlinksCreate/srv_zulip 1
```

The virtual machine needs to be shut down when you run this command.

#### Hyper-V error messages

If you get an error message on Windows about lack of Windows Home
support for Hyper-V when running `vagrant up`, the problem is that
Windows is incorrectly attempting to use Hyper-V rather than
Virtualbox as the virtualization provider. You can fix this by
explicitly passing the virtualbox provider to `vagrant up`:

```console
$ vagrant up --provide=virtualbox
```

#### Connection timeout on `vagrant up`

If you see the following error after running `vagrant up`:

```console
default: SSH address: 127.0.0.1:2222
default: SSH username: vagrant
default: SSH auth method: private key
default: Error: Connection timeout. Retrying...
default: Error: Connection timeout. Retrying...
default: Error: Connection timeout. Retrying...
```

A likely cause is that hardware virtualization is not enabled for your
computer. This must be done via your computer's BIOS settings. Look for a
setting called VT-x (Intel) or (AMD-V).

If this is already enabled in your BIOS, double-check that you are running a
64-bit operating system.

For further information about troubleshooting Vagrant timeout errors [see
this post](https://stackoverflow.com/questions/22575261/vagrant-stuck-connection-timeout-retrying#22575302).

#### VBoxManage errors related to VT-x or WHvSetupPartition

```console
There was an error while executing `VBoxManage`, a CLI used by Vagrant
for controlling VirtualBox. The command and stderr is shown below.

Command: ["startvm", "8924a681-b4e4-4b7a-96f2-4cb11619f123", "--type", "headless"]

Stderr: VBoxManage.exe: error: (VERR_NEM_MISSING_KERNEL_API).
VBoxManage.exe: error: VT-x is not available (VERR_VMX_NO_VMX)
VBoxManage.exe: error: Details: code E_FAIL (0x80004005), component ConsoleWrap, interface IConsole
```

or

```console
Stderr: VBoxManage.exe: error: Call to WHvSetupPartition failed: ERROR_SUCCESS (Last=0xc000000d/87) (VERR_NEM_VM_CREATE_FAILED)
VBoxManage.exe: error: Details: code E_FAIL (0x80004005), component ConsoleWrap, interface IConsole
```

First, ensure that hardware virtualization support (VT-x or AMD-V) is
enabled in your BIOS.

If the error persists, you may have run into an incompatibility
between VirtualBox and Hyper-V on Windows. To disable Hyper-V, open
command prompt as administrator, run
`bcdedit /set hypervisorlaunchtype off`, and reboot. If you need to
enable it later, run `bcdedit /deletevalue hypervisorlaunchtype`, and
reboot.

#### OSError: [Errno 26] Text file busy

```console
default: Traceback (most recent call last):
…
default:   File "/srv/zulip-py3-venv/lib/python3.6/shutil.py", line 426, in _rmtree_safe_fd
default:     os.rmdir(name, dir_fd=topfd)
default: OSError: [Errno 26] Text file busy: 'baremetrics'
```

This error is caused by a
[bug](https://www.virtualbox.org/ticket/19004) in recent versions of
the VirtualBox Guest Additions for Linux on Windows hosts. You can
check the running version of VirtualBox Guest Additions with this
command:

```console
$ vagrant ssh -- 'sudo modinfo -F version vboxsf'
```

The bug has not been fixed upstream as of this writing, but you may be
able to work around it by downgrading VirtualBox Guest Additions to
5.2.44. To do this, create a `~/.zulip-vagrant-config` file and add
this line:

```text
VBOXADD_VERSION 5.2.44
```

Then run these commands (yes, reload is needed twice):

```console
$ vagrant plugin install vagrant-vbguest
$ vagrant reload
$ vagrant reload --provision
```
