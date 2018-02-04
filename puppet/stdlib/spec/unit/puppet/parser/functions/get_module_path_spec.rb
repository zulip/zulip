#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe Puppet::Parser::Functions.function(:get_module_path) do
  Internals = PuppetlabsSpec::PuppetInternals
  class StubModule
    attr_reader :path
    def initialize(path)
      @path = path
    end
  end

  def scope(environment = "production")
    Internals.scope(:compiler => Internals.compiler(:node => Internals.node(:environment => environment)))
  end

  it 'should only allow one argument' do
    expect { scope.function_get_module_path([]) }.to raise_error(Puppet::ParseError, /Wrong number of arguments, expects one/)
    expect { scope.function_get_module_path(['1','2','3']) }.to raise_error(Puppet::ParseError, /Wrong number of arguments, expects one/)
  end
  it 'should raise an exception when the module cannot be found' do
    expect { scope.function_get_module_path(['foo']) }.to raise_error(Puppet::ParseError, /Could not find module/)
  end
  describe 'when locating a module' do
    let(:modulepath) { "/tmp/does_not_exist" }
    let(:path_of_module_foo) { StubModule.new("/tmp/does_not_exist/foo") }

    before(:each) { Puppet[:modulepath] = modulepath }

    it 'should be able to find module paths from the modulepath setting' do
      Puppet::Module.expects(:find).with('foo', 'production').returns(path_of_module_foo)
      scope.function_get_module_path(['foo']).should == path_of_module_foo.path
    end
    it 'should be able to find module paths when the modulepath is a list' do
      Puppet[:modulepath] = modulepath + ":/tmp"
      Puppet::Module.expects(:find).with('foo', 'production').returns(path_of_module_foo)
      scope.function_get_module_path(['foo']).should == path_of_module_foo.path
    end
    it 'should respect the environment' do
      pending("Disabled on Puppet 2.6.x") if Puppet.version =~ /^2\.6\b/
      Puppet.settings[:environment] = 'danstestenv'
      Puppet::Module.expects(:find).with('foo', 'danstestenv').returns(path_of_module_foo)
      scope('danstestenv').function_get_module_path(['foo']).should == path_of_module_foo.path
    end
  end
end
