#! /usr/bin/env ruby -S rspec
require 'spec_helper'

require 'rspec-puppet'
describe 'getparam' do
  describe 'when a resource is not specified' do
    it do
      should run.with_params().and_raise_error(ArgumentError)
      should run.with_params('User[dan]').and_raise_error(ArgumentError)
      should run.with_params('User[dan]', {}).and_raise_error(ArgumentError)
      should run.with_params('User[dan]', '').and_return('')
    end
  end
  describe 'when compared against a resource with no params' do
    let :pre_condition do
      'user { "dan": }'
    end
    it do
      should run.with_params('User[dan]', 'shell').and_return('')
    end
  end

  describe 'when compared against a resource with params' do
    let :pre_condition do
      'user { "dan": ensure => present, shell => "/bin/sh", managehome => false}'
    end
    it do
      should run.with_params('User[dan]', 'shell').and_return('/bin/sh')
      should run.with_params('User[dan]', '').and_return('')
      should run.with_params('User[dan]', 'ensure').and_return('present')
      should run.with_params('User[dan]', 'managehome').and_return(false)
    end
  end
end
