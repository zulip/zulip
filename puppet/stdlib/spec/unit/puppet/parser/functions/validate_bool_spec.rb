#! /usr/bin/env/ruby -S rspec

require 'spec_helper'

describe Puppet::Parser::Functions.function(:validate_bool) do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }
  describe 'when calling validate_bool from puppet' do

    %w{ true false }.each do |the_string|

      it "should not compile when #{the_string} is a string" do
        Puppet[:code] = "validate_bool('#{the_string}')"
        expect { scope.compiler.compile }.to raise_error(Puppet::ParseError, /is not a boolean/)
      end

      it "should compile when #{the_string} is a bare word" do
        Puppet[:code] = "validate_bool(#{the_string})"
        scope.compiler.compile
      end

    end

    it "should not compile when an arbitrary string is passed" do
      Puppet[:code] = 'validate_bool("jeff and dan are awesome")'
      expect { scope.compiler.compile }.to raise_error(Puppet::ParseError, /is not a boolean/)
    end

    it "should not compile when no arguments are passed" do
      Puppet[:code] = 'validate_bool()'
      expect { scope.compiler.compile }.to raise_error(Puppet::ParseError, /wrong number of arguments/)
    end

    it "should compile when multiple boolean arguments are passed" do
      Puppet[:code] = <<-'ENDofPUPPETcode'
        $foo = true
        $bar = false
        validate_bool($foo, $bar, true, false)
      ENDofPUPPETcode
      scope.compiler.compile
    end

    it "should compile when multiple boolean arguments are passed" do
      Puppet[:code] = <<-'ENDofPUPPETcode'
        $foo = true
        $bar = false
        validate_bool($foo, $bar, true, false, 'jeff')
      ENDofPUPPETcode
      expect { scope.compiler.compile }.to raise_error(Puppet::ParseError, /is not a boolean/)
    end
  end
end
