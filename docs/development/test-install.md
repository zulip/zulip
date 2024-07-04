# Testing the installer

Zulip's install process is tested as part of [its continuous
integrations suite][ci], but that only tests the most common
configurations; when making changes to more complicated [installation
options][installer-docs], Zulip provides tooling to repeatedly test
the installation process in a clean environment each time.

[ci]: https://github.com/zulip/zulip/actions/workflows/production-suite.yml?query=branch%3Amain
[installer-docs]: ../production/install.md

## Configuring

Using the test installer framework requires a Linux operating system;
it will not work on WSL, for instance. It requires at least 3G of
RAM, in order to accommodate the VMs and the steps which build the
release assets.

To begin, install the LXC toolchain:

```bash
sudo apt-get install lxc lxc-utils
```

All LXC commands (and hence many parts of the test installer) will
need to be run as root.

## Running a test install

### Build and unpack a release tarball

You only need to do this step once per time you work on a set of
changes, to refresh the package that the installer uses. The installer
doesn't work cleanly out of a source checkout; it wants a release
checkout, so we build a tarball of one of those first:

```bash
./tools/build-release-tarball test-installer
```

This will produce a file in /tmp, which it will print out the path to
as the last step; for example,
`/tmp/tmp.fepqqNBWxp/zulip-server-test-installer.tar.gz`

Next, unpack that file into a local directory; we will make any
changes we want in our source checkout and copy them into this
directory. The test installer needs the release directory to be named
`zulip-server`, so we rename it and move it appropriately. In the
first line, you'll need to substitute the actual path that you got for
the tarball, above:

```bash
tar xzf /tmp/tmp.fepqqNBWxp/zulip-server-test-installer.tar.gz
mkdir zulip-test-installer
mv zulip-server-test-installer zulip-test-installer/zulip-server
```

You should delete and re-create this `zulip-test-installer` directory
(using these steps) if you are working on a different installer
branch, or a significant time has passed since you last used it.

### Test an install

The `test-install` tooling takes a distribution release name
(e.g., "jammy"), the path to an unpacked release directory
or tarball, and then any of the normal options you want to pass down
into the installer.

For example, to test an install onto Ubuntu 22.04 "Jammy", we might
call:

```bash
sudo ./tools/test-install/install \
  -r jammy \
  ./zulip-test-installer/ \
  --hostname=zulip.example.net \
  --email=username@example.net
```

The first time you run this command for a given distribution, it will
build a "base" image for that to use on subsequent times; this will
take a while.

### See running containers after installation

Regardless of if the install succeeds or fails, it will stay running
so you can inspect it. You can see all of the containers which are
running, and their randomly-generated names, by running:

```bash
sudo lxc-ls -f
```

### Connect to a running container

After using `lxc-ls` to list containers, you can choose one of them
and connect to its terminal:

```bash
sudo lxc-attach --clear-env -n zulip-install-jammy-PUvff
```

### Stopping and destroying containers

To destroy all containers (but leave the base containers, which speed
up the initial install):

```bash
sudo ./tools/test-install/destroy-all -f
```

To destroy just one container:

```bash
sudo lxc-destroy -f -n zulip-install-jammy-PUvff
```

### Iterating on the installer

Iterate on the installer by making changes to your source tree,
copying them into the release directory, and re-running the installer,
which will start up a new container. Here, we update just the
`scripts` and `puppet` directories of the release directory:

```bash
rsync -az scripts puppet zulip-test-installer/zulip-server/

sudo ./tools/test-install/install \
 -r jammy \
 ./zulip-test-installer/ \
 --hostname=zulip.example.net \
 --email=username@example.net
```
