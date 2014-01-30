require 'spec_helper'
describe 'apt::ppa', :type => :define do
  [ { :lsbdistrelease => '11.04',
      :lsbdistcodename => 'natty',
      :package => 'python-software-properties'},
    { :lsbdistrelease => '12.10',
      :lsbdistcodename => 'quantal',
      :package => 'software-properties-common'},
  ].each do |platform|
    context "on #{platform[:lsbdistcodename]}" do
      let :facts do
        {
          :lsbdistrelease => platform[:lsbdistrelease],
          :lsbdistcodename => platform[:lsbdistcodename],
        }
      end
      let :release do
        "#{platform[:lsbdistcodename]}"
      end
      let :package do
        "#{platform[:package]}"
      end
      let :options do
        "-y"
      end
      ['ppa:dans_ppa', 'dans_ppa','ppa:dans-daily/ubuntu'].each do |t|
        describe "with title #{t}" do
          let :pre_condition do
            'class { "apt": }'
          end
          let :title do
            t
          end
          let :filename do
            t.sub(/^ppa:/,'').gsub('/','-') << "-" << "#{release}.list"
          end

          it { should contain_package("#{package}") }

          it { should contain_exec("apt_update").with(
            'command'     => '/usr/bin/apt-get update',
            'refreshonly' => true
            )
          }

          it { should contain_exec("add-apt-repository-#{t}").with(
            'command' => "/usr/bin/add-apt-repository #{options} #{t}",
            'unless'  => "/usr/bin/test -s /etc/apt/sources.list.d/#{filename}",
            'require' => ["File[/etc/apt/sources.list.d]", "Package[#{package}]"],
            'notify'  => "Exec[apt_update]"
            )
          }

          it { should create_file("/etc/apt/sources.list.d/#{filename}").with(
            'ensure'  => 'file',
            'require' => "Exec[add-apt-repository-#{t}]"
            )
          }
        end
      end
      describe 'without a proxy defined' do
        let :title do
          'rspec_ppa'
        end
        let :pre_condition do
          'class { "apt":
             proxy_host => false
          }'
        end
        let :filename do
          "#{title}-#{release}.list"
        end

        it { should contain_exec("add-apt-repository-#{title}").with(
          'environment' => [],
          'command'     => "/usr/bin/add-apt-repository #{options} #{title}",
          'unless'      => "/usr/bin/test -s /etc/apt/sources.list.d/#{filename}",
          'require'     => ["File[/etc/apt/sources.list.d]", "Package[#{package}]"],
          'notify'      => "Exec[apt_update]"
          )
        }
      end

      describe 'behind a proxy' do
        let :title do
          'rspec_ppa'
        end
        let :pre_condition do
          'class { "apt":
            proxy_host => "user:pass@proxy",
          }'
        end
          let :filename do
            "#{title}-#{release}.list"
          end

        it { should contain_exec("add-apt-repository-#{title}").with(
          'environment' => [
            "http_proxy=http://user:pass@proxy:8080",
            "https_proxy=http://user:pass@proxy:8080",
          ],
          'command'     => "/usr/bin/add-apt-repository #{options} #{title}",
          'unless'      => "/usr/bin/test -s /etc/apt/sources.list.d/#{filename}",
          'require'     => ["File[/etc/apt/sources.list.d]", "Package[#{package}]"],
          'notify'      => "Exec[apt_update]"
          )
        }
      end
    end
  end

  [ { :lsbdistcodename => 'natty', 
      :package => 'python-software-properties' },
    { :lsbdistcodename => 'quantal',
      :package => 'software-properties-common'},
  ].each do |platform|
    context "on #{platform[:lsbdistcodename]}" do
      describe "it should not error if package['#{platform[:package]}'] is already defined" do
        let :pre_condition do
           'class {"apt": }' +
           'package { "#{platform[:package]}": }->Apt::Ppa["ppa"]'
        end
        let :facts do
          {:lsbdistcodename => '#{platform[:lsbdistcodename]}'}
        end
        let(:title) { "ppa" }
        let(:release) { "#{platform[:lsbdistcodename]}" }
        it { should contain_package('#{platform[:package]}') }
      end
    end
  end

  describe "without Class[apt] should raise a Puppet::Error" do
    let(:release) { "natty" }
    let(:title) { "ppa" }
    it { expect { should contain_apt__ppa(title) }.to raise_error(Puppet::Error) }
  end

  describe "without release should raise a Puppet::Error" do
    let(:title) { "ppa:" }
    it { expect { should contain_apt__ppa(:release) }.to raise_error(Puppet::Error) }
  end
end
