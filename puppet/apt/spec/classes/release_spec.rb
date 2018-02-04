require 'spec_helper'
describe 'apt::release', :type => :class do
  let (:title) { 'my_package' }

  let :param_set do
    { :release_id => 'precise' }
  end

  let (:params) { param_set }

  it { should include_class("apt::params") }

  it {
    should contain_file("/etc/apt/apt.conf.d/01release").with({
      "mode"    => "0644",
      "owner"   => "root",
      "group"   => "root",
      "content" => "APT::Default-Release \"#{param_set[:release_id]}\";"
    })
  }
end

