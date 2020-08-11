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

# Workaround: Vagrant removed the atlas.hashicorp.com to
# vagrantcloud.com redirect in February 2018. The value of
# DEFAULT_SERVER_URL in Vagrant versions less than 1.9.3 is
# atlas.hashicorp.com, which means that removal broke the fetching and
# updating of boxes (since the old URL doesn't work).  See
# https://github.com/hashicorp/vagrant/issues/9442
if Vagrant::DEFAULT_SERVER_URL == "atlas.hashicorp.com"
  Vagrant::DEFAULT_SERVER_URL.replace('https://vagrantcloud.com')
end

# Monkey patch https://github.com/hashicorp/vagrant/pull/10879 so we
# can fall back to another provider if docker is not installed.
begin
  require Vagrant.source_root.join("plugins", "providers", "docker", "provider")
rescue LoadError
else
  VagrantPlugins::DockerProvider::Provider.class_eval do
    method(:usable?).owner == singleton_class or def self.usable?(raise_error=false)
      VagrantPlugins::DockerProvider::Driver.new.execute("docker", "version")
      true
    rescue Vagrant::Errors::CommandUnavailable, VagrantPlugins::DockerProvider::Errors::ExecuteError
      raise if raise_error
      return false
    end
  end
end

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  # The Zulip development environment runs on 9991 on the guest.
  host_port = 9991
  http_proxy = https_proxy = no_proxy = nil
  host_ip_addr = "127.0.0.1"

  # System settings for the virtual machine.
  vm_num_cpus = "2"
  vm_memory = "2048"

  ubuntu_mirror = ""

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
      when "GUEST_CPUS"; vm_num_cpus = value
      when "GUEST_MEMORY_MB"; vm_memory = value
      when "UBUNTU_MIRROR"; ubuntu_mirror = value
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
  config.vm.network "forwarded_port", guest: 9994, host: host_port + 3, host_ip: host_ip_addr
  # Specify Docker provider before VirtualBox provider so it's preferred.
  config.vm.provider "docker" do |d, override|
    d.build_dir = File.join(__dir__, "tools", "setup", "dev-vagrant-docker")
    d.build_args = ["--build-arg", "VAGRANT_UID=#{Process.uid}"]
    if !ubuntu_mirror.empty?
      d.build_args += ["--build-arg", "UBUNTU_MIRROR=#{ubuntu_mirror}"]
    end
    d.has_ssh = true
    d.create_args = ["--ulimit", "nofile=1024:65536"]
  end

  config.vm.provider "virtualbox" do |vb, override|
    override.vm.box = "hashicorp/bionic64"
    # It's possible we can get away with just 1.5GB; more testing needed
    vb.memory = vm_memory
    vb.cpus = vm_num_cpus
  end

  config.vm.provider "parallels" do |prl, override|
	override.vm.box = "bento/ubuntu-18.04"
	override.vm.box_version = "202005.21.0"
	prl.memory = vm_memory
	prl.cpus = vm_num_cpus
  end

$provision_script = <<SCRIPT
set -x
set -e
set -o pipefail

# Code should go here, rather than tools/provision, only if it is
# something that we don't want to happen when running provision in a
# development environment not using Vagrant.

# Set the Ubuntu mirror
[ ! '#{ubuntu_mirror}' ] || sudo sed -i 's|http://\\(\\w*\\.\\)*archive\\.ubuntu\\.com/ubuntu/\\? |#{ubuntu_mirror} |' /etc/apt/sources.list

# Set the MOTD on the system to have Zulip instructions
sudo ln -nsf /srv/zulip/tools/setup/dev-motd /etc/update-motd.d/99-zulip-dev
sudo rm -f /etc/update-motd.d/10-help-text
sudo dpkg --purge landscape-client landscape-common ubuntu-release-upgrader-core update-manager-core update-notifier-common ubuntu-server
sudo dpkg-divert --add --rename /etc/default/motd-news
sudo sh -c 'echo ENABLED=0 > /etc/default/motd-news'

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
    echo '    sudo chown -R 1000:$(id -g) /PATH/TO/ZULIP/CLONE'
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
