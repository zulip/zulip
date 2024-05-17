# -*- mode: ruby -*-

Vagrant.require_version ">= 2.2.6"

Vagrant.configure("2") do |config|
  # The Zulip development environment runs on 9991 on the guest.
  host_port = 9991
  http_proxy = https_proxy = no_proxy = nil
  host_ip_addr = "127.0.0.1"

  # System settings for the virtual machine.
  vm_num_cpus = "2"
  vm_memory = "2048"

  ubuntu_mirror = ""
  vboxadd_version = nil

  config.vm.box = "bento/ubuntu-22.04"

  config.vm.synced_folder ".", "/vagrant", disabled: true
  config.vm.synced_folder ".", "/srv/zulip", docker_consistency: "z"

  vagrant_config_file = ENV["HOME"] + "/.zulip-vagrant-config"
  if File.file?(vagrant_config_file)
    IO.foreach(vagrant_config_file) do |line|
      line.chomp!
      key, value = line.split(nil, 2)
      case key
      when /^([#;]|$)/ # ignore comments
      when "HTTP_PROXY"; http_proxy = value
      when "HTTPS_PROXY"; https_proxy = value
      when "NO_PROXY"; no_proxy = value
      when "HOST_PORT"; host_port = value.to_i
      when "HOST_IP_ADDR"; host_ip_addr = value
      when "GUEST_CPUS"; vm_num_cpus = value
      when "GUEST_MEMORY_MB"; vm_memory = value
      when "UBUNTU_MIRROR"; ubuntu_mirror = value
      when "VBOXADD_VERSION"; vboxadd_version = value
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
    puts "You have specified value for proxy in ~/.zulip-vagrant-config file but did not " \
         "install the vagrant-proxyconf plugin. To install it, run `vagrant plugin install " \
         "vagrant-proxyconf` in a terminal.  This error will appear twice."
    exit
  end

  config.vm.network "forwarded_port", guest: 9991, host: host_port, host_ip: host_ip_addr
  config.vm.network "forwarded_port", guest: 9994, host: host_port + 3, host_ip: host_ip_addr
  # Specify Docker provider before VirtualBox provider so it's preferred.
  config.vm.provider "docker" do |d, override|
    override.vm.box = nil
    d.build_dir = File.join(__dir__, "tools", "setup", "dev-vagrant-docker")
    d.build_args = ["--build-arg", "VAGRANT_UID=#{Process.uid}"]
    if !ubuntu_mirror.empty?
      d.build_args += ["--build-arg", "UBUNTU_MIRROR=#{ubuntu_mirror}"]
    end
    d.has_ssh = true
    d.create_args = ["--ulimit", "nofile=1024:65536"]
  end

  config.vm.provider "virtualbox" do |vb, override|
    # It's possible we can get away with just 1.5GB; more testing needed
    vb.memory = vm_memory
    vb.cpus = vm_num_cpus

    if !vboxadd_version.nil?
      override.vbguest.installer = Class.new(VagrantVbguest::Installers::Ubuntu) do
        define_method(:host_version) do |reload = false|
          VagrantVbguest::Version(vboxadd_version)
        end
      end
      override.vbguest.allow_downgrade = true
      override.vbguest.iso_path = "https://download.virtualbox.org/virtualbox/#{vboxadd_version}/VBoxGuestAdditions_#{vboxadd_version}.iso"
    end
  end

  config.vm.provider "hyperv" do |h, override|
    h.memory = vm_memory
    h.maxmemory = vm_memory
    h.cpus = vm_num_cpus
  end

  config.vm.provider "parallels" do |prl, override|
    prl.memory = vm_memory
    prl.cpus = vm_num_cpus
  end

  config.vm.provision "shell",
    # We want provision to be run with the permissions of the vagrant user.
    privileged: false,
    path: "tools/setup/vagrant-provision",
    env: { "UBUNTU_MIRROR" => ubuntu_mirror }
end
