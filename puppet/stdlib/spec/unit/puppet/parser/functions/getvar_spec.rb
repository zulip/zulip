#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe Puppet::Parser::Functions.function(:getvar) do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }
  describe 'when calling getvar from puppet' do

    it "should not compile when no arguments are passed" do
      pending("Fails on 2.6.x, see bug #15912") if Puppet.version =~ /^2\.6\./
      Puppet[:code] = '$foo = getvar()'
      expect {
        scope.compiler.compile
      }.to raise_error(Puppet::ParseError, /wrong number of arguments/)
    end

    it "should not compile when too many arguments are passed" do
      pending("Fails on 2.6.x, see bug #15912") if Puppet.version =~ /^2\.6\./
      Puppet[:code] = '$foo = getvar("foo::bar", "baz")'
      expect {
        scope.compiler.compile
      }.to raise_error(Puppet::ParseError, /wrong number of arguments/)
    end

    it "should lookup variables in other namespaces" do
      pending("Fails on 2.6.x, see bug #15912") if Puppet.version =~ /^2\.6\./
      Puppet[:code] = <<-'ENDofPUPPETcode'
        class site::data { $foo = 'baz' }
        include site::data
        $foo = getvar("site::data::foo")
        if $foo != 'baz' {
          fail('getvar did not return what we expect')
        }
      ENDofPUPPETcode
      scope.compiler.compile
    end
  end
end
