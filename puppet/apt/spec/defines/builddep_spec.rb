require 'spec_helper'
describe 'apt::builddep', :type => :define do

  let(:title) { 'my_package' }

  describe "should require apt-get update" do
    it { should contain_exec("apt_update").with({
        'command' => "/usr/bin/apt-get update",
        'refreshonly' => true
      })
    }
    it { should contain_anchor("apt::builddep::my_package").with({
        'require' => 'Class[Apt::Update]',
      })
    }
  end

end
