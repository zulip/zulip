require 'spec_helper'
describe 'apt::key', :type => :define do
  let :title do
    '8347A27F'
  end

  let :default_params do
    {
      :key         => title,
      :ensure      => 'present',
      :key_server  => "keyserver.ubuntu.com",
      :key_source  => false,
      :key_content => false
    }
  end

  [{},
    {
      :ensure  => 'absent'
    },
    {
      :ensure  => 'random'
    },
    {
      :key_source => 'ftp://ftp.example.org/key',
    },
    {
      :key_content => 'deadbeef',
    }
  ].each do |param_set|

    let :param_hash do
      param_hash = default_params.merge(param_set)
      param_hash[:key].upcase! if param_hash[:key]
      param_hash
    end

    let :params do
      param_set
    end

    let :digest do
      str = String.new
      str << param_hash[:key].to_s         << '/'
      str << param_hash[:key_content].to_s << '/'
      str << param_hash[:key_source].to_s  << '/'
      str << param_hash[:key_server].to_s  << '/'
      Digest::SHA1.hexdigest(str)
    end

    describe "when #{param_set == {} ? "using default" : "specifying"} define parameters" do

      it {
        if [:present, 'present', :absent, 'absent'].include? param_hash[:ensure]
          should contain_apt__params
        end
      }

      it {
        if [:present, 'present'].include? param_hash[:ensure]
          should_not contain_exec("apt::key #{param_hash[:key]} absent")
          should contain_anchor("apt::key #{param_hash[:key]} present")
          should contain_exec(digest).with({
            "path"    => "/bin:/usr/bin",
            "unless"  => "/usr/bin/apt-key list | /bin/grep '#{param_hash[:key]}'"
          })
        elsif [:absent, 'absent'].include? param_hash[:ensure]
          should_not contain_anchor("apt::key #{param_hash[:key]} present")
          should contain_exec("apt::key #{param_hash[:key]} absent").with({
            "path"    => "/bin:/usr/bin",
            "onlyif"  => "apt-key list | grep '#{param_hash[:key]}'",
            "command" => "apt-key del '#{param_hash[:key]}'"
          })
        else
          expect { should raise_error(Puppet::Error) }
        end
      }

      it {
        if [:present, 'present'].include? param_hash[:ensure]
          if param_hash[:key_content]
            should contain_exec(digest).with({
              "command" => "echo '#{param_hash[:key_content]}' | /usr/bin/apt-key add -"
            })
          elsif param_hash[:key_source]
            should contain_exec(digest).with({
              "command" => "wget -q '#{param_hash[:key_source]}' -O- | apt-key add -"
            })
          elsif param_hash[:key_server]
            should contain_exec(digest).with({
              "command" => "apt-key adv --keyserver '#{param_hash[:key_server]}' --recv-keys '#{param_hash[:key]}'"
            })
          end
        end
      }

    end
  end

  [{ :ensure => 'present' }, { :ensure => 'absent' }].each do |param_set|
    describe "should correctly handle duplicate definitions" do

      let :pre_condition do
        "apt::key { 'duplicate': key => '#{title}'; }"
      end

      let(:params) { param_set }

      it {
        if param_set[:ensure] == 'present'
          should contain_anchor("apt::key #{title} present")
          should contain_apt__key(title)
          should contain_apt__key("duplicate")
        elsif param_set[:ensure] == 'absent'
          expect { should raise_error(Puppet::Error) }
        end
      }

    end
  end

end

