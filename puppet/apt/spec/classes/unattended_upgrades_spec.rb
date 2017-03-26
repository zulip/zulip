require 'spec_helper'
describe 'apt::unattended_upgrades', :type => :class do
  let(:file_unattended) { '/etc/apt/apt.conf.d/50unattended-upgrades' }
  let(:file_periodic) { '/etc/apt/apt.conf.d/10periodic' }

  it { should contain_package("unattended-upgrades") }

  it {
    should create_file("/etc/apt/apt.conf.d/50unattended-upgrades").with({
      "owner"   => "root",
      "group"   => "root",
      "mode"    => "0644",
      "require" => "Package[unattended-upgrades]",
    })
  }

  it {
    should create_file("/etc/apt/apt.conf.d/10periodic").with({
      "owner"   => "root",
      "group"   => "root",
      "mode"    => "0644",
      "require" => "Package[unattended-upgrades]",
    })
  }

  describe "origins" do
    describe "with param defaults" do
      let(:params) {{ }}
      it { should contain_file(file_unattended).with_content(/^Unattended-Upgrade::Allowed-Origins \{\n\t"\${distro_id}:\${distro_codename}-security";\n\};$/) }
    end

    describe "with origins => ['ubuntu:precise-security']" do
      let :params do
        { :origins => ['ubuntu:precise-security'] }
      end
      it { should contain_file(file_unattended).with_content(/^Unattended-Upgrade::Allowed-Origins \{\n\t"ubuntu:precise-security";\n\};$/) }
    end
  end

  describe "blacklist" do
    describe "with param defaults" do
      let(:params) {{ }}
      it { should contain_file(file_unattended).with_content(/^Unattended-Upgrade::Package-Blacklist \{\n\};$/) }
    end

    describe "with blacklist => []" do
      let :params do
        { :blacklist => ['libc6', 'libc6-dev'] }
      end
      it { should contain_file(file_unattended).with_content(/^Unattended-Upgrade::Package-Blacklist \{\n\t"libc6";\n\t"libc6-dev";\n\};$/) }
    end
  end

  describe "with update => 2" do
    let :params do
      { :update => "2" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::Update-Package-Lists "2";$/) }
  end

  describe "with download => 2" do
    let :params do
      { :download => "2" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::Download-Upgradeable-Packages "2";$/) }
  end

  describe "with upgrade => 2" do
    let :params do
      { :upgrade => "2" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::Unattended-Upgrade "2";$/) }
  end

  describe "with autoclean => 2" do
    let :params do
      { :autoclean => "2" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::AutocleanInterval "2";$/) }
  end

  describe "with auto_fix => false" do
    let :params do
      { :auto_fix => false }
    end
    it { should contain_file(file_unattended).with_content(/^Unattended-Upgrade::AutoFixInterruptedDpkg "false";$/) }
  end

  describe "with minimal_steps => true" do
    let :params do
      { :minimal_steps => true }
    end
    it { should contain_file(file_unattended).with_content(/^Unattended-Upgrade::MinimalSteps "true";$/) }
  end

  describe "with install_on_shutdown => true" do
    let :params do
      { :install_on_shutdown => true }
    end
    it { should contain_file(file_unattended).with_content(/^Unattended-Upgrade::InstallOnShutdown "true";$/) }
  end

  describe "mail_to" do
    describe "param defaults" do
      let(:params) {{ }}
      it { should_not contain_file(file_unattended).with_content(/^Unattended-Upgrade::Mail /) }
      it { should_not contain_file(file_unattended).with_content(/^Unattended-Upgrade::MailOnlyOnError /) }
    end

    describe "with mail_to => user@website, mail_only_on_error => true" do
      let :params do
        { :mail_to => "user@website",
          :mail_only_on_error => true }
      end
      it { should contain_file(file_unattended).with_content(/^Unattended-Upgrade::Mail "user@website";$/) }
      it { should contain_file(file_unattended).with_content(/^Unattended-Upgrade::MailOnlyOnError "true";$/) }
    end
  end

  describe "with remove_unused => false" do
    let :params do
      { :remove_unused => false }
    end
    it { should contain_file(file_unattended).with_content(/^Unattended-Upgrade::Remove-Unused-Dependencies "false";$/) }
  end

  describe "with auto_reboot => true" do
    let :params do
      { :auto_reboot => true }
    end
    it { should contain_file(file_unattended).with_content(/^Unattended-Upgrade::Automatic-Reboot "true";$/) }
  end

  describe "dl_limit" do
    describe "param defaults" do
      let(:params) {{ }}
      it { should_not contain_file(file_unattended).with_content(/^Acquire::http::Dl-Limit /) }
    end

    describe "with dl_limit => 70" do
      let :params do
        { :dl_limit => "70" }
      end
      it { should contain_file(file_unattended).with_content(/^Acquire::http::Dl-Limit "70";$/) }
    end
  end

  describe "with enable => 0" do
    let :params do
      { :enable => "0" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::Enable "0";$/) }
  end

  describe "with backup_interval => 1" do
    let :params do
      { :backup_interval => "1" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::BackUpArchiveInterval "1";$/) }
  end

  describe "with backup_level => 0" do
    let :params do
      { :backup_level => "0" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::BackUpLevel "0";$/) }
  end

  describe "with max_age => 1" do
    let :params do
      { :max_age => "1" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::MaxAge "1";$/) }
  end

  describe "with min_age => 1" do
    let :params do
      { :min_age => "1" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::MinAge "1";$/) }
  end

  describe "with max_size => 1" do
    let :params do
      { :max_size => "1" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::MaxSize "1";$/) }
  end

  describe "with download_delta => 2" do
    let :params do
      { :download_delta => "2" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::Download-Upgradeable-Packages-Debdelta "2";$/) }
  end

  describe "with verbose => 2" do
    let :params do
      { :verbose => "2" }
    end
    it { should contain_file(file_periodic).with_content(/^APT::Periodic::Verbose "2";$/) }
  end

end
