# -*- mode: ruby -*-

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  # For LXC. VirtualBox hosts use a different box, described below.
  config.vm.box = "fgrehm/trusty64-lxc"

  # The Zulip development environment runs on 9991 on the guest.
  config.vm.network "forwarded_port", guest: 9991, host: 9991, host_ip: "127.0.0.1"

  config.vm.synced_folder ".", "/vagrant", disabled: true
  config.vm.synced_folder ".", "/srv/zulip"

  config.vm.provider "virtualbox" do |vb, override|
    override.vm.box = "ubuntu/trusty64"
    # 2GiB seemed reasonable here. The VM OOMs with only 1024MiB.
    vb.memory = 2048
  end

$provision_script = <<SCRIPT
set -x
set -e
sudo apt-get update
sudo apt-get install -y python-pbs
python /srv/zulip/provision.py
SCRIPT

  config.vm.provision "shell",
    # We want provision.py to be run with the permissions of the vagrant user.
    privileged: false,
    inline: $provision_script
end
