#! /usr/bin/env ruby -S rspec

require 'spec_helper'

describe Puppet::Parser::Functions.function(:validate_hash) do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  describe 'when calling validate_hash from puppet' do

    %w{ true false }.each do |the_string|

      it "should not compile when #{the_string} is a string" do
        Puppet[:code] = "validate_hash('#{the_string}')"
        expect { scope.compiler.compile }.to raise_error(Puppet::ParseError, /is not a Hash/)
      end

      it "should not compile when #{the_string} is a bare word" do
        Puppet[:code] = "validate_hash(#{the_string})"
        expect { scope.compiler.compile }.to raise_error(Puppet::ParseError, /is not a Hash/)
      end

    end

    it "should compile when multiple hash arguments are passed" do
      Puppet[:code] = <<-'ENDofPUPPETcode'
        $foo = {}
        $bar = { 'one' => 'two' }
        validate_hash($foo, $bar)
      ENDofPUPPETcode
      scope.compiler.compile
    end

    it "should not compile when an undef variable is passed" do
      Puppet[:code] = <<-'ENDofPUPPETcode'
        $foo = undef
        validate_hash($foo)
      ENDofPUPPETcode
      expect { scope.compiler.compile }.to raise_error(Puppet::ParseError, /is not a Hash/)
    end

  end

end
