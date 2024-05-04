If your preferred editor is Visual Studio Code, the [Visual Studio
Code Remote - SSH](https://code.visualstudio.com/docs/remote/ssh)
extension is recommended for editing files when developing with
Vagrant. When you have it installed, you can run:

```console
$ code .
```

to open VS Code connected to your Vagrant environment. See the
[Remote development over SSH][remote-ssh] tutorial for more information.

When using this plugin with Vagrant, you will want to run the command
`vagrant ssh-config` from your `zulip` folder:

```console
$ vagrant ssh-config
Host default
  HostName 127.0.0.1
  User vagrant
  Port 2222
  UserKnownHostsFile /dev/null
  StrictHostKeyChecking no
  PasswordAuthentication no
  IdentityFile /PATH/TO/zulip/.vagrant/machines/default/docker/private_key
  IdentitiesOnly yes
  LogLevel FATAL
  PubkeyAcceptedKeyTypes +ssh-rsa
  HostKeyAlgorithms +ssh-rsa
```

Then copy that config into your `~/.ssh/config` file. You may want to change
the host name from `default` to something more descriptive, like `zulip`.
Finally, refresh the known remotes in Visual Studio Code's Remote Explorer.
