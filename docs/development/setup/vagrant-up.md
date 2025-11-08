The first time you run this command it will take some time because Vagrant
does the following:

- downloads the base Ubuntu 22.04 virtual machine/Docker image
- configures this virtual machine/container for use with Zulip,
- creates a shared directory mapping your clone of the Zulip code inside the
  virtual machine/container at `~/zulip`
- runs the `./tools/provision` script inside the virtual machine/container, which
  downloads all required dependencies, sets up the Python environment for
  the Zulip development server, and initializes a default test
  database. We call this process "provisioning", and it is documented
  in some detail in our [dependencies documentation](/subsystems/dependencies.md).

You will need an active internet connection during the entire
process. (See [Specifying a proxy](/development/setup-recommended.md#specifying-a-proxy) if you need a
proxy to access the internet.) `vagrant up` can fail while
provisioning if your Internet connection is unreliable. To retry, you
can use `vagrant provision` (`vagrant up` will just boot the guest
without provisioning after the first time). Other common issues are
documented in the
[Troubleshooting and common errors](/development/setup-recommended.md#troubleshooting-and-common-errors)
section. If that doesn't help, please visit
[#provision help](https://chat.zulip.org/#narrow/channel/21-provision-help)
in the [Zulip development community server](https://zulip.com/development-community/) for
real-time help.
