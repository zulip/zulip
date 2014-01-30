require 'spec_helper'
require 'facter/util/puppet_settings'

describe Facter::Util::PuppetSettings do

  describe "#with_puppet" do
    context "Without Puppet loaded" do
      before(:each) do
        Module.expects(:const_get).with("Puppet").raises(NameError)
      end

      it 'should be nil' do
        subject.with_puppet { Puppet[:vardir] }.should be_nil
      end
      it 'should not yield to the block' do
        Puppet.expects(:[]).never
        subject.with_puppet { Puppet[:vardir] }.should be_nil
      end
    end
    context "With Puppet loaded" do
      module Puppet; end
      let(:vardir) { "/var/lib/puppet" }

      before :each do
        Puppet.expects(:[]).with(:vardir).returns vardir
      end
      it 'should yield to the block' do
        subject.with_puppet { Puppet[:vardir] }
      end
      it 'should return the nodes vardir' do
        subject.with_puppet { Puppet[:vardir] }.should eq vardir
      end
    end
  end
end
