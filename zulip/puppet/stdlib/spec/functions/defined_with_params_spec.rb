#! /usr/bin/env ruby -S rspec
require 'spec_helper'

require 'rspec-puppet'
describe 'defined_with_params' do
  describe 'when a resource is not specified' do
    it { should run.with_params().and_raise_error(ArgumentError) }
  end
  describe 'when compared against a resource with no attributes' do
    let :pre_condition do
      'user { "dan": }'
    end
    it do
      should run.with_params('User[dan]', {}).and_return(true)
      should run.with_params('User[bob]', {}).and_return(false)
      should run.with_params('User[dan]', {'foo' => 'bar'}).and_return(false)
    end
  end

  describe 'when compared against a resource with attributes' do
    let :pre_condition do
      'user { "dan": ensure => present, shell => "/bin/csh", managehome => false}'
    end
    it do
      should run.with_params('User[dan]', {}).and_return(true)
      should run.with_params('User[dan]', '').and_return(true)
      should run.with_params('User[dan]', {'ensure' => 'present'}
                            ).and_return(true)
      should run.with_params('User[dan]',
                             {'ensure' => 'present', 'managehome' => false}
                            ).and_return(true)
      should run.with_params('User[dan]',
                             {'ensure' => 'absent', 'managehome' => false}
                            ).and_return(false)
    end
  end
end
