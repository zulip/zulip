##### 2. Add yourself to the `docker` group:

```console
$ sudo adduser $USER docker
Adding user `YOURUSERNAME' to group `docker' ...
Adding user YOURUSERNAME to group docker
Done.
```

You will need to reboot for this change to take effect. If it worked,
you will see `docker` in your list of groups:

```console
$ groups | grep docker
YOURUSERNAME adm cdrom sudo dip plugdev lpadmin sambashare docker
```

##### 3. Make sure the Docker daemon is running:

If you had previously installed and removed an older version of
Docker, an [Ubuntu
bug](https://bugs.launchpad.net/ubuntu/+source/docker.io/+bug/1844894)
may prevent Docker from being automatically enabled and started after
installation. You can check using the following:

```console
$ systemctl status docker
● docker.service - Docker Application Container Engine
   Loaded: loaded (/lib/systemd/system/docker.service; enabled; vendor preset: enabled)
   Active: active (running) since Mon 2019-07-15 23:20:46 IST; 18min ago
```

If the service is not running, you'll see `Active: inactive (dead)` on
the second line, and will need to enable and start the Docker service
using the following:

```console
$ sudo systemctl unmask docker
$ sudo systemctl enable docker
$ sudo systemctl start docker
```
