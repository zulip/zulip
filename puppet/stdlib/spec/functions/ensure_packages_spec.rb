#! /usr/bin/env ruby

require 'spec_helper'
require 'rspec-puppet'

describe 'ensure_packages' do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  describe 'argument handling' do
    it 'fails with no arguments' do
      should run.with_params().and_raise_error(Puppet::ParseError)
    end
    it 'requires an array' do
      lambda { scope.function_ensure_packages([['foo']]) }.should_not raise_error
    end
    it 'fails when given a string' do
      should run.with_params('foo').and_raise_error(Puppet::ParseError)
    end
  end

  context 'given a catalog containing Package[puppet]{ensure => absent}' do
    let :pre_condition do
      'package { puppet: ensure => absent }'
    end

    # NOTE: should run.with_params has the side effect of making the compiler
    # available to the test harness.
    it 'has no effect on Package[puppet]' do
      should run.with_params(['puppet'])
      rsrc = compiler.catalog.resource('Package[puppet]')
      rsrc.to_hash.should == {:ensure => "absent"}
    end
  end

  context 'given a clean catalog' do
    it 'declares package resources with ensure => present' do
      should run.with_params(['facter'])
      rsrc = compiler.catalog.resource('Package[facter]')
      rsrc.to_hash.should == {:name => "facter", :ensure => "present"}
    end
  end
end
