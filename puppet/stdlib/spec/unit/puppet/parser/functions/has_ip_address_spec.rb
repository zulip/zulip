#!/usr/bin/env ruby -S rspec
require 'spec_helper'

describe Puppet::Parser::Functions.function(:has_ip_address) do

  let(:scope) do
    PuppetlabsSpec::PuppetInternals.scope
  end

  subject do
    function_name = Puppet::Parser::Functions.function(:has_ip_address)
    scope.method(function_name)
  end

  context "On Linux Systems" do
    before :each do
      scope.stubs(:lookupvar).with('interfaces').returns('eth0,lo')
      scope.stubs(:lookupvar).with('ipaddress').returns('10.0.2.15')
      scope.stubs(:lookupvar).with('ipaddress_eth0').returns('10.0.2.15')
      scope.stubs(:lookupvar).with('ipaddress_lo').returns('127.0.0.1')
    end

    it 'should have primary address (10.0.2.15)' do
      subject.call(['10.0.2.15']).should be_true
    end

    it 'should have lookupback address (127.0.0.1)' do
      subject.call(['127.0.0.1']).should be_true
    end

    it 'should not have other address' do
      subject.call(['192.1681.1.1']).should be_false
    end

    it 'should not have "mspiggy" on an interface' do
      subject.call(['mspiggy']).should be_false
    end
  end
end
