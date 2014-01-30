require 'spec_helper'

describe Puppet::Parser::Functions.function(:validate_cmd) do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  # The subject of these examplres is the method itself.
  subject do
    # This makes sure the function is loaded within each test
    function_name = Puppet::Parser::Functions.function(:validate_cmd)
    scope.method(function_name)
  end

  context 'Using Puppet::Parser::Scope.new' do

    describe 'Garbage inputs' do
      inputs = [
        [ nil ],
        [ [ nil ] ],
        [ { 'foo' => 'bar' } ],
        [ { } ],
        [ '' ],
        [ "one", "one", "MSG to User", "4th arg" ],
      ]

      inputs.each do |input|
        it "validate_cmd(#{input.inspect}) should fail" do
          expect { subject.call [input] }.to raise_error Puppet::ParseError
        end
      end
    end

    describe 'Valid inputs' do
      inputs = [
        [ '/full/path/to/something', '/bin/echo' ],
        [ '/full/path/to/something', '/bin/cat' ],
      ]

      inputs.each do |input|
        it "validate_cmd(#{input.inspect}) should not fail" do
          expect { subject.call input }.not_to raise_error
        end
      end
    end

    describe "Valid inputs which should raise an exception without a message" do
      # The intent here is to make sure valid inputs raise exceptions when they
      # don't specify an error message to display.  This is the behvior in
      # 2.2.x and prior.
      inputs = [
        [ "hello", "/bin/false" ],
      ]

      inputs.each do |input|
        it "validate_cmd(#{input.inspect}) should fail" do
          expect { subject.call input }.to raise_error /validate_cmd.*?failed to validate content with command/
        end
      end
    end

    describe "Nicer Error Messages" do
      # The intent here is to make sure the function returns the 3rd argument
      # in the exception thrown
      inputs = [
        [ "hello", [ "bye", "later", "adios" ], "MSG to User" ],
        [ "greetings", "salutations", "Error, greetings does not match salutations" ],
      ]

      inputs.each do |input|
        it "validate_cmd(#{input.inspect}) should fail" do
          expect { subject.call input }.to raise_error /#{input[2]}/
        end
      end
    end

    describe "Test output message" do
      it "validate_cmd('whatever', 'kthnksbye') should fail" do
          expect { subject.call ['whatever', 'kthnksbye'] }.to raise_error /kthnksbye.* returned 1/
      end
    end
  end
end
