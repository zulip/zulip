# Puppet Enterprise requires the following facts to be set in order to operate.
# These facts are set using the file ???? and the two facts are
# `fact_stomp_port`, and `fact_stomp_server`.
#

require 'spec_helper'

describe "External facts in /etc/puppetlabs/facter/facts.d/puppet_enterprise_installer.txt" do
  context "With Facter 1.6.17 which does not have external facts support" do
    before :each do
      Facter.stubs(:version).returns("1.6.17")
      # Stub out the filesystem for stdlib
      Dir.stubs(:entries).with("/etc/puppetlabs/facter/facts.d").
        returns(['puppet_enterprise_installer.txt'])
      Dir.stubs(:entries).with("/etc/facter/facts.d").returns([])
      File.stubs(:readlines).with('/etc/puppetlabs/facter/facts.d/puppet_enterprise_installer.txt').
        returns([
          "fact_stomp_port=61613\n",
          "fact_stomp_server=puppetmaster.acme.com\n",
          "fact_is_puppetagent=true\n",
          "fact_is_puppetmaster=false\n",
          "fact_is_puppetca=false\n",
          "fact_is_puppetconsole=false\n",
      ])
      if Facter.collection.respond_to? :load
        Facter.collection.load(:facter_dot_d)
      else
        Facter.collection.loader.load(:facter_dot_d)
      end
    end

    it 'defines fact_stomp_port' do
      Facter.fact(:fact_stomp_port).value.should == '61613'
    end
    it 'defines fact_stomp_server' do
      Facter.fact(:fact_stomp_server).value.should == 'puppetmaster.acme.com'
    end
    it 'defines fact_is_puppetagent' do
      Facter.fact(:fact_is_puppetagent).value.should == 'true'
    end
    it 'defines fact_is_puppetmaster' do
      Facter.fact(:fact_is_puppetmaster).value.should == 'false'
    end
    it 'defines fact_is_puppetca' do
      Facter.fact(:fact_is_puppetca).value.should == 'false'
    end
    it 'defines fact_is_puppetconsole' do
      Facter.fact(:fact_is_puppetconsole).value.should == 'false'
    end
  end

  [ '1.7.1', '2.0.1' ].each do |v|
    context "With Facter #{v} which has external facts support" do
      before :each do
        Facter.stubs(:version).returns(v)
      end

      it 'does not call Facter::Util::DotD.new' do
        Facter::Util::DotD.expects(:new).never

        if Facter.collection.respond_to? :load
          Facter.collection.load(:facter_dot_d)
        else
          Facter.collection.loader.load(:facter_dot_d)
        end
      end
    end
  end
end
