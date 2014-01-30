#! /usr/bin/env ruby -S rspec
require 'spec_helper'

describe Puppet::Parser::Functions.function(:has_key) do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  describe 'when calling has_key from puppet' do
    it "should not compile when no arguments are passed" do
      pending("Fails on 2.6.x, see bug #15912") if Puppet.version =~ /^2\.6\./
      Puppet[:code] = '$x = has_key()'
      expect {
        scope.compiler.compile
      }.to raise_error(Puppet::ParseError, /wrong number of arguments/)
    end

    it "should not compile when 1 argument is passed" do
      pending("Fails on 2.6.x, see bug #15912") if Puppet.version =~ /^2\.6\./
      Puppet[:code] = "$x = has_key('foo')"
      expect {
        scope.compiler.compile
      }.to raise_error(Puppet::ParseError, /wrong number of arguments/)
    end

    it "should require the first value to be a Hash" do
      pending("Fails on 2.6.x, see bug #15912") if Puppet.version =~ /^2\.6\./
      Puppet[:code] = "$x = has_key('foo', 'bar')"
      expect {
        scope.compiler.compile
      }.to raise_error(Puppet::ParseError, /expects the first argument to be a hash/)
    end
  end

  describe 'when calling the function has_key from a scope instance' do
    it 'should detect existing keys' do
      scope.function_has_key([{'one' => 1}, 'one']).should be_true
    end

    it 'should detect existing keys' do
      scope.function_has_key([{'one' => 1}, 'two']).should be_false
    end
  end
end
