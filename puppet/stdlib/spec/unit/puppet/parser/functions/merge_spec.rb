#! /usr/bin/env ruby -S rspec

require 'spec_helper'

describe Puppet::Parser::Functions.function(:merge) do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  describe 'when calling merge from puppet' do
    it "should not compile when no arguments are passed" do
      pending("Fails on 2.6.x, see bug #15912") if Puppet.version =~ /^2\.6\./
      Puppet[:code] = '$x = merge()'
      expect {
        scope.compiler.compile
      }.to raise_error(Puppet::ParseError, /wrong number of arguments/)
    end

    it "should not compile when 1 argument is passed" do
      pending("Fails on 2.6.x, see bug #15912") if Puppet.version =~ /^2\.6\./
      Puppet[:code] = "$my_hash={'one' => 1}\n$x = merge($my_hash)"
      expect {
        scope.compiler.compile
      }.to raise_error(Puppet::ParseError, /wrong number of arguments/)
    end
  end

  describe 'when calling merge on the scope instance' do
    it 'should require all parameters are hashes' do
      expect { new_hash = scope.function_merge([{}, '2'])}.to raise_error(Puppet::ParseError, /unexpected argument type String/)
    end

    it 'should be able to merge two hashes' do
      new_hash = scope.function_merge([{'one' => '1', 'two' => '1'}, {'two' => '2', 'three' => '2'}])
      new_hash['one'].should   == '1'
      new_hash['two'].should   == '2'
      new_hash['three'].should == '2'
    end

    it 'should merge multiple hashes' do
      hash = scope.function_merge([{'one' => 1}, {'one' => '2'}, {'one' => '3'}])
      hash['one'].should == '3'
    end

    it 'should accept empty hashes' do
      scope.function_merge([{},{},{}]).should == {}
    end
  end
end
