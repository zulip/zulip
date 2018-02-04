#! /usr/bin/env ruby -S rspec

require 'spec_helper'

describe Puppet::Parser::Functions.function(:validate_string) do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  describe 'when calling validate_string from puppet' do

    %w{ foo bar baz }.each do |the_string|

      it "should compile when #{the_string} is a string" do
        Puppet[:code] = "validate_string('#{the_string}')"
        scope.compiler.compile
      end

      it "should compile when #{the_string} is a bare word" do
        Puppet[:code] = "validate_string(#{the_string})"
        scope.compiler.compile
      end

    end

    %w{ true false }.each do |the_string|
      it "should compile when #{the_string} is a string" do
        Puppet[:code] = "validate_string('#{the_string}')"
        scope.compiler.compile
      end

      it "should not compile when #{the_string} is a bare word" do
        Puppet[:code] = "validate_string(#{the_string})"
        expect { scope.compiler.compile }.to raise_error(Puppet::ParseError, /is not a string/)
      end
    end

    it "should compile when multiple string arguments are passed" do
      Puppet[:code] = <<-'ENDofPUPPETcode'
        $foo = ''
        $bar = 'two'
        validate_string($foo, $bar)
      ENDofPUPPETcode
      scope.compiler.compile
    end

    it "should compile when an explicitly undef variable is passed (NOTE THIS MAY NOT BE DESIRABLE)" do
      Puppet[:code] = <<-'ENDofPUPPETcode'
        $foo = undef
        validate_string($foo)
      ENDofPUPPETcode
      scope.compiler.compile
    end

    it "should compile when an undefined variable is passed (NOTE THIS MAY NOT BE DESIRABLE)" do
      Puppet[:code] = <<-'ENDofPUPPETcode'
        validate_string($foobarbazishouldnotexist)
      ENDofPUPPETcode
      scope.compiler.compile
    end
  end
end
