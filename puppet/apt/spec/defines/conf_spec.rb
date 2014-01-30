require 'spec_helper'
describe 'apt::conf', :type => :define do
  let :title do
    'norecommends'
  end

  describe "when creating an apt preference" do
    let :params do
      {
        :priority => '00',
        :content  => "Apt::Install-Recommends 0;\nApt::AutoRemove::InstallRecommends 1;\n"
      }
    end

    let :filename do
      "/etc/apt/apt.conf.d/00norecommends"
    end

    it { should contain_apt__conf('norecommends').with({
         'priority' => '00',
         'content'  => "Apt::Install-Recommends 0;\nApt::AutoRemove::InstallRecommends 1;\n"
      })
    }

    it { should contain_file(filename).with({
          'ensure'    => 'present',
          'content'   => "Apt::Install-Recommends 0;\nApt::AutoRemove::InstallRecommends 1;\n",
          'owner'     => 'root',
          'group'     => 'root',
          'mode'      => '0644',
        })
      }
  end

  describe "when removing an apt preference" do
    let :params do
      {
        :ensure   => 'absent',
        :priority => '00',
        :content  => "Apt::Install-Recommends 0;\nApt::AutoRemove::InstallRecommends 1;\n"
      }
    end

    let :filename do
      "/etc/apt/apt.conf.d/00norecommends"
    end

    it { should contain_file(filename).with({
        'ensure'    => 'absent',
        'content'   => "Apt::Install-Recommends 0;\nApt::AutoRemove::InstallRecommends 1;\n",
        'owner'     => 'root',
        'group'     => 'root',
        'mode'      => '0644',
      })
    }
  end
end
