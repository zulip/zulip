require 'spec_helper'
describe 'apt::source', :type => :define do
  let :title do
    'my_source'
  end

  let :default_params do
    {
      :ensure             => 'present',
      :location           => '',
      :release            => 'karmic',
      :repos              => 'main',
      :include_src        => true,
      :required_packages  => false,
      :key                => false,
      :key_server         => 'keyserver.ubuntu.com',
      :key_content        => false,
      :key_source         => false,
      :pin                => false
    }
  end

  [{},
   {
      :location           => 'http://example.com',
      :release            => 'precise',
      :repos              => 'security',
      :include_src        => false,
      :required_packages  => 'apache',
      :key                => 'key_name',
      :key_server         => 'keyserver.debian.com',
      :pin                => '600',
      :key_content        => 'ABCD1234'
    },
    {
      :key                => 'key_name',
      :key_server         => 'keyserver.debian.com',
      :key_content        => false,
    },
    {
      :ensure             => 'absent',
      :location           => 'http://example.com',
      :release            => 'precise',
      :repos              => 'security',
    },
    {
      :release            => '',
    },
    {
      :release            => 'custom',
    },
    {
      :architecture       => 'amd64',
    }
  ].each do |param_set|
    describe "when #{param_set == {} ? "using default" : "specifying"} class parameters" do
      let :param_hash do
        default_params.merge(param_set)
      end

      let :facts do
        {:lsbdistcodename => 'karmic'}
      end

      let :params do
        param_set
      end

      let :filename do
        "/etc/apt/sources.list.d/#{title}.list"
      end

      let :content do
        content = "# #{title}"
        if param_hash[:architecture]
          arch = "[arch=#{param_hash[:architecture]}]"
        end
        content << "\ndeb #{arch}#{param_hash[:location]} #{param_hash[:release]} #{param_hash[:repos]}\n"

        if param_hash[:include_src]
          content << "deb-src #{arch}#{param_hash[:location]} #{param_hash[:release]} #{param_hash[:repos]}\n"
        end
        content
      end

      it { should contain_apt__params }

      it { should contain_file("#{title}.list").with({
          'ensure'    => param_hash[:ensure],
          'path'      => filename,
          'owner'     => 'root',
          'group'     => 'root',
          'mode'      => '0644',
          'content'   => content,
        })
      }

      it {
        if param_hash[:pin]
          should contain_apt__pin(title).with({
            "priority"  => param_hash[:pin],
            "before"    => "File[#{title}.list]"
          })
        else
          should_not contain_apt__pin(title).with({
            "priority"  => param_hash[:pin],
            "before"    => "File[#{title}.list]"
          })
        end
      }

      it {
        should contain_exec("apt_update").with({
          "command"     => "/usr/bin/apt-get update",
          "refreshonly" => true
        })
      }

      it {
        if param_hash[:required_packages]
          should contain_exec("Required packages: '#{param_hash[:required_packages]}' for #{title}").with({
            "command" => "/usr/bin/apt-get -y install #{param_hash[:required_packages]}",
            "subscribe"   => "File[#{title}.list]",
            "refreshonly" => true,
            "before"      => 'Exec[apt_update]',
          })
        else
          should_not contain_exec("Required packages: '#{param_hash[:required_packages]}' for #{title}").with({
            "command"     => "/usr/bin/apt-get -y install #{param_hash[:required_packages]}",
            "subscribe"   => "File[#{title}.list]",
            "refreshonly" => true
          })
        end
      }

      it {
        if param_hash[:key]
          should contain_apt__key("Add key: #{param_hash[:key]} from Apt::Source #{title}").with({
            "key"         => param_hash[:key],
            "ensure"      => :present,
            "key_server"  => param_hash[:key_server],
            "key_content" => param_hash[:key_content],
            "key_source"  => param_hash[:key_source],
            "before"      => "File[#{title}.list]"
          })
        else
          should_not contain_apt__key("Add key: #{param_hash[:key]} from Apt::Source #{title}").with({
            "key"         => param_hash[:key],
            "ensure"      => :present,
            "key_server"  => param_hash[:key_server],
            "key_content" => param_hash[:key_content],
            "key_source"  => param_hash[:key_source],
            "before"      => "File[#{title}.list]"
          })
        end
      }
    end
  end
  describe "without release should raise a Puppet::Error" do
    let(:default_params) { Hash.new }
    let(:facts) { Hash.new }
    it { expect { should raise_error(Puppet::Error) } }
    let(:facts) { { :lsbdistcodename => 'lucid' } }
    it { should contain_apt__source(title) }
  end
end
