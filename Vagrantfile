# -*- mode: ruby -*-

VAGRANTFILE_API_VERSION = "2"

def command?(name)
  `which #{name} > /dev/null 2>&1`
  $?.success?
end

if Vagrant::VERSION == "1.8.7" then
    path = `which curl`
    if path.include?('/opt/vagrant/embedded/bin/curl') then
        puts "In Vagrant 1.8.7, curl is broken. Please use Vagrant 2.0.2 "\
             "or run 'sudo rm -f /opt/vagrant/embedded/bin/curl' to fix the "\
             "issue before provisioning. See "\
             "https://github.com/mitchellh/vagrant/issues/7997 "\
             "for reference."
        exit
    end
end

# Workaround: the lxc-config in vagrant-lxc is incompatible with changes in
# LXC 2.1.0, found in Ubuntu 17.10 artful.  LXC 2.1.1 (in 18.04 LTS bionic)
# ignores the old config key, so this will only be needed for artful.
#
# vagrant-lxc upstream has an attempted fix:
#   https://github.com/fgrehm/vagrant-lxc/issues/445
# but it didn't work in our testing.  This is a temporary issue, so we just
# hack in a fix: we patch the skeleton `lxc-config` file right in the
# distribution of the vagrant-lxc "box" we use.  If the user doesn't yet
# have the box (e.g. on first setup), Vagrant would download it but too
# late for us to patch it like this; so we prompt them to explicitly add it
# first and then rerun.
if ['up', 'provision'].include? ARGV[0]
  if command? "lxc-ls"
    LXC_VERSION = `lxc-ls --version`.strip unless defined? LXC_VERSION
    if LXC_VERSION == "2.1.0"
      lxc_config_file = ENV['HOME'] + "/.vagrant.d/boxes/fgrehm-VAGRANTSLASH-trusty64-lxc/1.2.0/lxc/lxc-config"
      if File.file?(lxc_config_file)
        lines = File.readlines(lxc_config_file)
        deprecated_line = "lxc.pivotdir = lxc_putold\n"
        if lines[1] == deprecated_line
          lines[1] = "# #{deprecated_line}"
          File.open(lxc_config_file, 'w') do |f|
            f.puts(lines)
          end
        end
      else
        puts 'You are running LXC 2.1.0, and fgrehm/trusty64-lxc box is incompatible '\
            "with it by default. First add the box by doing:\n"\
            "  vagrant box add  https://vagrantcloud.com/fgrehm/trusty64-lxc\n"\
            'Once this command succeeds, do "vagrant up" again.'
        exit
      end
    end
  end
end

# Workaround: Vagrant removed the atlas.hashicorp.com to
# vagrantcloud.com redirect in February 2018. The value of
# DEFAULT_SERVER_URL in Vagrant versions less than 1.9.3 is
# atlas.hashicorp.com, which means that removal broke the fetching and
# updating of boxes (since the old URL doesn't work).  See
# https://github.com/hashicorp/vagrant/issues/9442
if Vagrant::DEFAULT_SERVER_URL == "atlas.hashicorp.com"
  Vagrant::DEFAULT_SERVER_URL.replace('https://vagrantcloud.com')
end

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  # For LXC. VirtualBox hosts use a different box, described below.
  config.vm.box = "fgrehm/trusty64-lxc"

  # The Zulip development environment runs on 9991 on the guest.
  host_port = 9991
  http_proxy = https_proxy = no_proxy = nil
  host_ip_addr = "127.0.0.1"

  config.vm.synced_folder ".", "/vagrant", disabled: true
  if (/darwin/ =~ RUBY_PLATFORM) != nil
    config.vm.synced_folder ".", "/srv/zulip", type: "nfs",
        linux__nfs_options: ['rw']
    config.vm.network "private_network", type: "dhcp"
  else
    config.vm.synced_folder ".", "/srv/zulip"
  end

  vagrant_config_file = ENV['HOME'] + "/.zulip-vagrant-config"
  if File.file?(vagrant_config_file)
    IO.foreach(vagrant_config_file) do |line|
      line.chomp!
      key, value = line.split(nil, 2)
      case key
      when /^([#;]|$)/; # ignore comments
      when "HTTP_PROXY"; http_proxy = value
      when "HTTPS_PROXY"; https_proxy = value
      when "NO_PROXY"; no_proxy = value
      when "HOST_PORT"; host_port = value.to_i
      when "HOST_IP_ADDR"; host_ip_addr = value
      end
    end
  end

  if Vagrant.has_plugin?("vagrant-proxyconf")
    if !http_proxy.nil?
      config.proxy.http = http_proxy
    end
    if !https_proxy.nil?
      config.proxy.https = https_proxy
    end
    if !no_proxy.nil?
      config.proxy.no_proxy = no_proxy
    end
  elsif !http_proxy.nil? or !https_proxy.nil?
    # This prints twice due to https://github.com/hashicorp/vagrant/issues/7504
    # We haven't figured out a workaround.
    puts 'You have specified value for proxy in ~/.zulip-vagrant-config file but did not ' \
         'install the vagrant-proxyconf plugin. To install it, run `vagrant plugin install ' \
         'vagrant-proxyconf` in a terminal.  This error will appear twice.'
    exit
  end

  config.vm.network "forwarded_port", guest: 9991, host: host_port, host_ip: host_ip_addr
  # Specify LXC provider before VirtualBox provider so it's preferred.
  config.vm.provider "lxc" do |lxc|
    if command? "lxc-ls"
      LXC_VERSION = `lxc-ls --version`.strip unless defined? LXC_VERSION
      if LXC_VERSION >= "1.1.0"
        # Allow start without AppArmor, otherwise Box will not Start on Ubuntu 14.10
        # see https://github.com/fgrehm/vagrant-lxc/issues/333
        lxc.customize 'aa_allow_incomplete', 1
      end
      if LXC_VERSION >= "2.0.0"
        lxc.backingstore = 'dir'
      end
    end
  end

  config.vm.provider "virtualbox" do |vb, override|
    override.vm.box = "ubuntu/trusty64"
    # It's possible we can get away with just 1.5GB; more testing needed
    vb.memory = 2048
    vb.cpus = 2
  end

  config.vm.provider "vmware_fusion" do |vb, override|
    override.vm.box = "puphpet/ubuntu1404-x64"
    vb.vmx["memsize"] = "2048"
    vb.vmx["numvcpus"] = "2"
  end

$provision_script = <<SCRIPT
set -x
set -e
set -o pipefail

# Code should go here, rather than tools/provision, only if it is
# something that we don't want to happen when running provision in a
# development environment not using Vagrant.

# Set the MOTD on the system to have Zulip instructions
sudo rm -f /etc/update-motd.d/*
sudo bash -c 'cat << EndOfMessage > /etc/motd
Welcome to the Zulip development environment!  Popular commands:
* tools/provision - Update the development environment
* tools/run-dev.py - Run the development server
* tools/lint - Run the linter (quick and catches many problmes)
* tools/test-* - Run tests (use --help to learn about options)

Read https://zulip.readthedocs.io/en/latest/testing/testing.html to learn
how to run individual test suites so that you can get a fast debug cycle.

EndOfMessage'

# If the host is running SELinux remount the /sys/fs/selinux directory as read only,
# needed for apt-get to work.
if [ -d "/sys/fs/selinux" ]; then
    sudo mount -o remount,ro /sys/fs/selinux
fi

# Set default locale, this prevents errors if the user has another locale set.
if ! grep -q 'LC_ALL=en_US.UTF-8' /etc/default/locale; then
    echo "LC_ALL=en_US.UTF-8" | sudo tee -a /etc/default/locale
fi

# Set an environment variable, so that we won't print the virtualenv
# shell warning (it'll be wrong, since the shell is dying anyway)
export SKIP_VENV_SHELL_WARNING=1

# End `set -x`, so that the end of provision doesn't look like an error
# message after a successful run.
set +x

# Check if the zulip directory is writable
if [ ! -w /srv/zulip ]; then
    echo "The vagrant user is unable to write to the zulip directory."
    echo "To fix this, run the following commands on the host machine:"
    # sudo is required since our uid is not 1000
    echo '    vagrant halt -f'
    echo '    rm -rf /PATH/TO/ZULIP/CLONE/.vagrant'
    echo '    sudo chown -R 1000:$(whoami) /PATH/TO/ZULIP/CLONE'
    echo "Replace /PATH/TO/ZULIP/CLONE with the path to where zulip code is cloned."
    echo "You can resume setting up your vagrant environment by running:"
    echo "    vagrant up"
    exit 1
fi
# Provision the development environment
ln -nsf /srv/zulip ~/zulip
/srv/zulip/tools/provision

# Run any custom provision hooks the user has configured
if [ -f /srv/zulip/tools/custom_provision ]; then
    chmod +x /srv/zulip/tools/custom_provision
    /srv/zulip/tools/custom_provision
fi
SCRIPT

  config.vm.provision "shell",
    # We want provision to be run with the permissions of the vagrant user.
    privileged: false,
    inline: $provision_script
end
