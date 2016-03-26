# -*- mode: ruby -*-

VAGRANTFILE_API_VERSION = "2"

module OS
    def OS.windows?
        (/cygwin|mswin|mingw|bccwin|wince|emx/ =~ RUBY_PLATFORM) != nil
    end

    def OS.mac?
        (/darwin/ =~ RUBY_PLATFORM) != nil
    end

    def OS.unix?
        !OS.windows?
    end

    def OS.linux?
        OS.unix? and not OS.mac?
    end
end

def command?(name)
  `which #{name}`
  $?.success?
end

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  # For LXC. VirtualBox hosts use a different box, described below.
  config.vm.box = "fgrehm/trusty64-lxc"

  # The Zulip development environment runs on 9991 on the guest.
  config.vm.network "forwarded_port", guest: 9991, host: 9991, host_ip: "127.0.0.1"

  config.vm.synced_folder ".", "/vagrant", disabled: true
  config.vm.synced_folder ".", "/srv/zulip"

  # Specify LXC provider before VirtualBox provider so it's preferred.
  config.vm.provider "lxc" do |lxc|
    if command? "lxc-ls"
      LXC_VERSION = `lxc-ls --version`.strip unless defined? LXC_VERSION
      if LXC_VERSION >= "1.1.0"
        # Allow start without AppArmor, otherwise Box will not Start on Ubuntu 14.10
        # see https://github.com/fgrehm/vagrant-lxc/issues/333
        lxc.customize 'aa_allow_incomplete', 1
      end
    end
  end

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
/usr/bin/python /srv/zulip/provisions/provision_all_systems_before.py
if OS.windows?
  /usr/bin/python /srv/zulip/provisions/provision_windows.py
end
else
  /usr/bin/python /srv/zulip/provisions/provision_non_windows.py
end
/usr/bin/python /srv/zulip/provisions/provision_all_systems_after.py
SCRIPT

  config.vm.provision "shell",
    # We want provision.py to be run with the permissions of the vagrant user.
    privileged: false,
    inline: $provision_script
end
