#!/usr/bin/env ruby -S rspec
require 'spec_helper'

describe Puppet::Parser::Functions.function(:has_ip_network) do

  let(:scope) do
    PuppetlabsSpec::PuppetInternals.scope
  end

  subject do
    function_name = Puppet::Parser::Functions.function(:has_ip_network)
    scope.method(function_name)
  end

  context "On Linux Systems" do
    before :each do
      scope.stubs(:lookupvar).with('interfaces').returns('eth0,lo')
      scope.stubs(:lookupvar).with('network').returns(:undefined)
      scope.stubs(:lookupvar).with('network_eth0').returns('10.0.2.0')
      scope.stubs(:lookupvar).with('network_lo').returns('127.0.0.1')
    end

    it 'should have primary network (10.0.2.0)' do
      subject.call(['10.0.2.0']).should be_true
    end

    it 'should have loopback network (127.0.0.0)' do
      subject.call(['127.0.0.1']).should be_true
    end

    it 'should not have other network' do
      subject.call(['192.168.1.0']).should be_false
    end
  end
end

