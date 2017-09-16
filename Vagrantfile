# -*- mode: ruby -*-

VAGRANTFILE_API_VERSION = "2"

def command?(name)
  `which #{name} > /dev/null 2>&1`
  $?.success?
end

if Vagrant::VERSION == "1.8.7" then
    path = `which curl`
    if path.include?('/opt/vagrant/embedded/bin/curl') then
        puts "In Vagrant 1.8.7, curl is broken. Please use Vagrant 1.8.6 "\
             "or run 'sudo rm -f /opt/vagrant/embedded/bin/curl' to fix the "\
             "issue before provisioning. See "\
             "https://github.com/mitchellh/vagrant/issues/7997 "\
             "for reference."
        exit
    end
end

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  # For LXC. VirtualBox hosts use a different box, described below.
  config.vm.box = "fgrehm/trusty64-lxc"

  # The Zulip development environment runs on 9991 on the guest.
  host_port = 9991
  http_proxy = https_proxy = no_proxy = nil
  host_ip_addr = "127.0.0.1"

  config.vm.synced_folder ".", "/vagrant", disabled: true
  config.vm.synced_folder ".", "/srv/zulip"

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
# If the host is running SELinux remount the /sys/fs/selinux directory as read only,
# needed for apt-get to work.
if [ -d "/sys/fs/selinux" ]; then
  sudo mount -o remount,ro /sys/fs/selinux
fi

# Set default locale, this prevents errors if the user has another locale set.
if ! grep -q 'LC_ALL=en_US.UTF-8' /etc/default/locale; then
    echo "LC_ALL=en_US.UTF-8" | sudo tee -a /etc/default/locale
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
