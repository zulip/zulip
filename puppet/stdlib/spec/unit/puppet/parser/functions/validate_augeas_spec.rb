require 'spec_helper'

describe Puppet::Parser::Functions.function(:validate_augeas), :if => Puppet.features.augeas? do
  let(:scope) { PuppetlabsSpec::PuppetInternals.scope }

  # The subject of these examplres is the method itself.
  subject do
    # This makes sure the function is loaded within each test
    function_name = Puppet::Parser::Functions.function(:validate_augeas)
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
        it "validate_augeas(#{input.inspect}) should fail" do
          expect { subject.call [input] }.to raise_error Puppet::ParseError
        end
      end
    end

    describe 'Valid inputs' do
      inputs = [
        [ "root:x:0:0:root:/root:/bin/bash\n", 'Passwd.lns' ],
        [ "proc /proc   proc    nodev,noexec,nosuid     0       0\n", 'Fstab.lns'],
      ]

      inputs.each do |input|
        it "validate_augeas(#{input.inspect}) should not fail" do
          expect { subject.call input }.not_to raise_error
        end
      end
    end

    describe "Valid inputs which should raise an exception without a message" do
      # The intent here is to make sure valid inputs raise exceptions when they
      # don't specify an error message to display.  This is the behvior in
      # 2.2.x and prior.
      inputs = [
        [ "root:x:0:0:root\n", 'Passwd.lns' ],
        [ "127.0.1.1\n", 'Hosts.lns' ],
      ]

      inputs.each do |input|
        it "validate_augeas(#{input.inspect}) should fail" do
          expect { subject.call input }.to raise_error /validate_augeas.*?matched less than it should/
        end
      end
    end

    describe "Nicer Error Messages" do
      # The intent here is to make sure the function returns the 3rd argument
      # in the exception thrown
      inputs = [
        [ "root:x:0:0:root\n", 'Passwd.lns', [], 'Failed to validate passwd content' ],
        [ "127.0.1.1\n", 'Hosts.lns', [], 'Wrong hosts content' ],
      ]

      inputs.each do |input|
        it "validate_augeas(#{input.inspect}) should fail" do
          expect { subject.call input }.to raise_error /#{input[2]}/
        end
      end
    end

    describe "Passing simple unit tests" do
      inputs = [
        [ "root:x:0:0:root:/root:/bin/bash\n", 'Passwd.lns', ['$file/foobar']],
        [ "root:x:0:0:root:/root:/bin/bash\n", 'Passwd.lns', ['$file/root/shell[.="/bin/sh"]', 'foobar']],
      ]

      inputs.each do |input|
        it "validate_augeas(#{input.inspect}) should fail" do
          expect { subject.call input }.not_to raise_error
        end
      end
    end

    describe "Failing simple unit tests" do
      inputs = [
        [ "foobar:x:0:0:root:/root:/bin/bash\n", 'Passwd.lns', ['$file/foobar']],
        [ "root:x:0:0:root:/root:/bin/sh\n", 'Passwd.lns', ['$file/root/shell[.="/bin/sh"]', 'foobar']],
      ]

      inputs.each do |input|
        it "validate_augeas(#{input.inspect}) should fail" do
          expect { subject.call input }.to raise_error /testing path/
        end
      end
    end
  end
end
